from typing import Literal

from app.core.registry import service_registry
from app.services.data_product.models.request_new_data_product import (
    RequestNewDataProductRequest,
    RequestNewDataProductResponse,
)
from app.services.data_product.utils.common_utils import (
    normalize_date_string_to_datetime_utc,
    check_if_date_in_future,
)
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.logging import LOGGER, auto_context


@service_registry.tool(
    name="data_product_request_new_data_product",
    description="""
    This tool is used to request a new data product.
    Example: 'Request a new data product with <name>, <overview>, <business_justification>, <key_features>, <privacy>'
    Args:
        name (str): TThe name of the request.
        overview (str): A brief overview of the data product you are requesting.
        business_justification (str): The business justification for the data product you are requesting. Reasons why this data is required.
        key_features (str): The key features you expect in the data product you are requesting.
        privacy (Literal[
            "Yes - I need access to the sensitive information.",
            "No - I do not require access to sensitive information.",
        ]): If you need access to the sensitive information in the data product.
        due_date (str | None): [Optional] The due date for the data product request. This should be a date value in the format 'YYYY-MM-DD'.
        domain (str | None): [Optional] The business domain for the data product.
        sample (str | None): [Optional] URL or description of sample of the requested data product.
        delivery_methods (list[str] | None): [Optional] List of delivery methods of the requested new data product.
        sharing_requirements (List[
            Literal[
                "Yes - I need to share this data with users who are internal to my organization.",
                "Yes - I need to share this data with users who are external to my organization.",
            ]
        ] | None): [Optional] Sharing requirements for the requested data product.
        data_quality (str | None): [Optional] Data quality expectations for the requested data product.
        refresh_frequency (str | None): [Optional] Frequency to refresh the requested data product.
    """,
    tags={"request", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def request_new_data_product(
    request: RequestNewDataProductRequest,
) -> RequestNewDataProductResponse:
    LOGGER.info(
        f"Requesting a new data product with following details: {request.name=}, {request.overview=}, {request.business_justification=}, {request.key_features=}, {request.privacy=}."
    )

    if request.due_date:
        date_value = normalize_date_string_to_datetime_utc(request.due_date)
        check_if_date_in_future(date_value)
        request.due_date = date_value

    payload = get_data_product_request_payload(request)

    response = await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_product_request",
        json=payload,
        tool_name="data_product_request_new_data_product",
    )

    LOGGER.info("Data product request created successfully.")
    return RequestNewDataProductResponse(
        message=f"Data product request created successfully and it is currently in {response['state']} state.",
        url=f"{tool_helper_service.ui_base_url}/governance/workflow/tasks?context=df",
    )


def get_data_product_request_payload(request: RequestNewDataProductRequest) -> dict:
    payload = {
        "name": request.name,
        "due_date": request.due_date,
        "data_product_content": {
            "overview": request.overview,
            "sample": {"text": request.sample},
            "business_justification": request.business_justification,
            "key_features": request.key_features,
        },
        "data_contract": {
            "privacy": request.privacy,
            "data_quality": request.data_quality,
            "refresh_frequency": request.refresh_frequency,
        },
    }

    if request.domain:
        payload["domain"] = {"name": request.domain}

    if request.delivery_methods:
        delivery_methods = request.delivery_methods
        set_delivery_methods(payload, delivery_methods)

    if request.sharing_requirements:
        sharing_requirements = request.sharing_requirements
        set_sharing_requirements(payload, sharing_requirements)

    return payload


def set_delivery_methods(payload: dict, delivery_methods) -> None:
    if isinstance(delivery_methods, list):
        payload["data_product_content"]["delivery_methods"] = [
            {"name": dm} for dm in delivery_methods
        ]
    else:
        payload["data_product_content"]["delivery_methods"] = [
            {"name": delivery_methods}
        ]


def set_sharing_requirements(payload: dict, sharing_requirements) -> None:
    if isinstance(sharing_requirements, list):
        payload["data_contract"]["sharing_requirements"] = {
            "intents": sharing_requirements
        }
    else:
        payload["data_contract"]["sharing_requirements"] = {
            "intents": [sharing_requirements]
        }


@service_registry.tool(
    name="data_product_request_new_data_product",
    description="""
    This tool is used to request a new data product.
    Example: 'Request a new data product with <name>, <overview>, <business_justification>, <key_features>, <privacy>'
    Args:
        name (str): TThe name of the request.
        overview (str): A brief overview of the data product you are requesting.
        business_justification (str): The business justification for the data product you are requesting. Reasons why this data is required.
        key_features (str): The key features you expect in the data product you are requesting.
        privacy (Literal[
            "Yes - I need access to the sensitive information.",
            "No - I do not require access to sensitive information.",
        ]): If you need access to the sensitive information in the data product.
        due_date (str | None): [Optional] The due date for the data product request. This should be a date value in the format 'YYYY-MM-DD'.
        domain (str | None): [Optional] The business domain for the data product.
        sample (str | None): [Optional] URL or description of sample of the requested data product.
        delivery_methods (list[str] | None): [Optional] List of delivery methods of the requested new data product.
        sharing_requirements (List[
            Literal[
                "Yes - I need to share this data with users who are internal to my organization.",
                "Yes - I need to share this data with users who are external to my organization.",
            ]
        ] | None): [Optional] Sharing requirements for the requested data product.
        data_quality (str | None): [Optional] Data quality expectations for the requested data product.
        refresh_frequency (str | None): [Optional] Frequency to refresh the requested data product.
    """,
    tags={"request", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def wxo_request_new_data_product(
    name: str,
    overview: str,
    business_justification: str,
    key_features: str,
    privacy: Literal[
        "Yes - I need access to the sensitive information.",
        "No - I do not require access to sensitive information.",
        "No - I cannot use the data if it contains sensitive information.",
        "N/A",
    ],
    due_date: str | None = None,
    domain: str | None = None,
    sample: str | None = None,
    delivery_methods: list[str] | None = None,
    sharing_requirements: list[Literal[
                "Yes - I need to share this data with users who are internal to my organization.",
                "Yes - I need to share this data with users who are external to my organization.",
            ]] | None = None,
    data_quality: str | None = None,
    refresh_frequency: str | None = None,
) -> str:
    """Watsonx Orchestrator compatible version that expands RequestNewDataProductRequest object into individual parameters."""

    request = RequestNewDataProductRequest(
        name=name,
        overview=overview,
        business_justification=business_justification,
        key_features=key_features,
        privacy=privacy,
        due_date=due_date,
        domain=domain,
        sample=sample,
        delivery_methods=delivery_methods,
        sharing_requirements=sharing_requirements,
        data_quality=data_quality,
        refresh_frequency=refresh_frequency,
    )

    # Call the original request_new_data_product function
    return await request_new_data_product(request)