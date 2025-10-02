# this file has been modified with the assistance of Bob
# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Literal

from app.core.auth import get_access_token
from app.core.registry import service_registry
from app.core.settings import settings
from app.services.constants import ASSISTANT_BASE_ENDPOINT
from app.services.data_quality.models.get_data_quality_for_asset import (
    DataQuality,
    GetDataQualityForAssetRequest,
    GetDataQualityForAssetResponse,
)
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.http_client import get_http_client


@service_registry.tool(
    name="data_quality_get_data_quality_for_asset",
    description="""Retrieve data quality metrics and information for a specific asset.
    
    This tool fetches quality metrics for a data asset, including overall quality score and
    specific dimensions: consistency, validity, and completeness. This information helps
    assess the reliability and usability of the data.""",
    tags={"data_quality", "metrics", "quality"},
    meta={"version": "1.0", "service": "data_quality"},
)
@auto_context
async def get_data_quality_for_asset(
    request: GetDataQualityForAssetRequest,
) -> GetDataQualityForAssetResponse:
    LOGGER.info(
        f"Calling get_data_quality_for_asset with asset_id: {request.asset_id}, "
        f"asset_name: {request.asset_name}, container_id: {request.container_id}, "
        f"container_type: {request.container_type}"
    )

    payload = {
        "operation_type": "get_data_quality",
        "get_data_quality_request": {
            "asset_id": request.asset_id,
            "asset_name": request.asset_name,
            "catalog_id": (
                request.container_id if request.container_type == "catalog" else "dummy"
            ),
            "project_id": (
                request.container_id if request.container_type == "project" else None
            ),
        },
    }

    auth = await get_access_token()
    headers = {"Content-Type": "application/json", "Authorization": auth}

    client = get_http_client()

    try:
        response = await client.post(
            settings.di_service_url + ASSISTANT_BASE_ENDPOINT,
            data=payload,
            headers=headers,
        )

        assets = response.get("assets")

        if not assets:
            raise ServiceError(
                f"Asset {request.asset_id} in {request.container_type} {request.container_id} was not found."
            )

        dq = assets[0].get("data_quality")

        if assets and dq:
            data_quality = DataQuality.model_validate(dq)
            if "<ui_base_url>" in data_quality.report_url:
                data_quality.report_url = data_quality.report_url.replace(
                    "<ui_base_url>", f"{settings.ui_url}"
                )
            return GetDataQualityForAssetResponse(
                data_quality=DataQuality.model_validate(data_quality)
            )
        else:
            raise ServiceError(
                f"Asset {request.asset_id} in {request.container_type} {request.container_id} has no data quality data."
            )

    except ExternalAPIError:
        # This will catch HTTP errors (4xx, 5xx) that were raised by raise_for_status()
        raise
    except Exception as e:
        raise ServiceError(f"Failed to get data quality: {str(e)}")


@service_registry.tool(
    name="data_quality_get_data_quality_for_asset",
    description="""Retrieve data quality metrics and information for a specific asset.
    
    This tool fetches quality metrics for a data asset, including overall quality score and
    specific dimensions: consistency, validity, and completeness. This information helps
    assess the reliability and usability of the data.""",
    tags={"data_quality", "metrics", "quality"},
    meta={"version": "1.0", "service": "data_quality"},
)
@auto_context
async def wxo_get_data_quality_for_asset(
    asset_id: str,
    asset_name: str,
    container_id: str,
    container_type: Literal["catalog", "project"],
) -> GetDataQualityForAssetResponse:
    """Watsonx Orchestrator compatible version of get_data_quality_for_asset."""

    request = GetDataQualityForAssetRequest(
        asset_id=asset_id,
        asset_name=asset_name,
        container_id=container_id,
        container_type=container_type,
    )

    # Call the original function
    return await get_data_quality_for_asset(request)
