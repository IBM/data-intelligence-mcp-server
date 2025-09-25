# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from functools import wraps

from app.core.auth import get_access_token, get_dph_catalog_id_for_user


async def get_dph_catalog_id():
    token = await get_access_token()
    return await get_dph_catalog_id_for_user(token)


# This methods adds `@CATALOG_ID` at the end of the given field name in an object.
def add_catalog_id_suffix(param_name="request", field_name="data_product_draft_id"):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import inspect

            suffix = f"@{await get_dph_catalog_id()}"

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
