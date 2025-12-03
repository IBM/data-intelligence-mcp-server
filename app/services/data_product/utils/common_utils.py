# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from functools import wraps
from datetime import date, timezone, datetime
from urllib.parse import urlencode

from app.shared.exceptions.base import ServiceError
from app.shared.utils.tool_helper_service import tool_helper_service
from app.services.constants import PROJECTS_BASE_ENDPOINT
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import append_context_to_url
from aiocache import cached


@cached(ttl=3300)  # 55 minutes - shorter than 1 hour token expiration
async def get_dph_catalog_id_for_user() -> str:
    LOGGER.info("In get_dph_catalog_id_for_user, getting DPH catalog id")
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/v2/catalogs/ibm-default-hub"
    )
    return response.get("metadata", {}).get("guid", "")


# This methods adds `@CATALOG_ID` at the end of the given field name in an object.
def add_catalog_id_suffix(param_name="request", field_name="data_product_draft_id"):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import inspect

            suffix = f"@{await get_dph_catalog_id_for_user()}"

            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            model = bound_args.arguments.get(param_name)
            if model is not None and hasattr(model, field_name):
                value = getattr(model, field_name)
                if isinstance(value, str) and "@" not in value:
                    setattr(model, field_name, f"{value}{suffix}")

            return await func(*bound_args.args, **bound_args.kwargs)

        return wrapper

    return decorator


def get_data_product_url(product_id: str, state: str):
    query_params = {
            "page_id": "UI_PRODUCT_DETAIL_PAGE",
            "productState": state,
            "version_id": product_id.split("@")[0] if "@" in product_id else product_id
        }
    return append_context_to_url(f"{tool_helper_service.ui_base_url}/dpx/?{urlencode(query_params)}")



async def get_dph_default_project_id(bss_account_id) -> str:
    query_params = {
        "name": "Default Data Product Delivery Project",
        "include": "fields",
        "bss_account_id": bss_account_id,
    }
    response = await tool_helper_service.execute_get_request(
        f"{tool_helper_service.base_url}{PROJECTS_BASE_ENDPOINT}",
        params=query_params,
    )
    resources = response.get("resources")
    if resources and len(resources) > 0:
        return resources[0].get("metadata", {}).get("guid", "")
    return ""


def normalize_date_string_to_datetime_utc(date_value: str) -> str:
    """
    Convert a date object to the required string format \"yyyy-MM-dd'T'HH:mm:ss.SSSXXX\".

    Args:
        date_value (str): The date string to be converted.

    Returns:
        str: The date in \"yyyy-MM-dd'T'HH:mm:ss.SSSXXX\" format.
    """
    try:
        parsed_date = date.fromisoformat(date_value)
        return parsed_date.strftime("%Y-%m-%dT00:00:00.000Z")
    except ValueError:
        raise ServiceError(
            f"Invalid date format: '{date_value}'. Please provide the date in 'YYYY-MM-DD' format."
        )
    
        
    
def check_if_date_in_future(date_value: str):
    """
    Checks if the date is in future. If not, this raises a ToolProcessFailedError.

    Args:
        date_value (str): The date string to be checked.
    """
    date = datetime.strptime(date_value, "%Y-%m-%dT%H:%M:%S.%fZ")
    date = date.replace(tzinfo=timezone.utc)

    today = datetime.now(timezone.utc).date()

    if date.date() < today:
        raise ServiceError(
            f"Invalid date value: '{date_value}'. Please provide the date in future."
        )


@auto_context
def validate_inputs(request, *fields_to_validate):
    required_fields = fields_to_validate

    for field in required_fields:
        value = getattr(request, field, None)
        if not value:
            msg = f"{field.capitalize()} is a mandatory field. Please input the value for {field.capitalize()}."
            LOGGER.error(msg)
            raise ServiceError(msg)
