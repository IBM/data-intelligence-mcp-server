# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from typing import Literal

from app.core.auth import get_access_token
from app.core.registry import service_registry
from app.core.settings import settings
from app.services.constants import DATA_QUALITY_BASE_ENDPOINT
from app.services.data_quality.models.get_data_quality_for_asset import (
    DataQuality,
    GetDataQualityForAssetRequest,
    GetDataQualityForAssetResponse,
)
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import append_context_to_url
from app.shared.utils.helpers import is_uuid
from app.shared.utils.http_client import get_http_client


async def retrieve_data_quality_id_for_asset(
    asset_id: str, container_id: str, container_type: Literal["project", "catalog"]
) -> str:
    """
    Find id of data quality for data asset

    Args:
        asset_id: str: Asset id
        container_id: str: Container id
        container_type: str: Container type (project or catalog)

    Returns:
        uuid.UUID: Unique identifier of the data quality asset.
    """

    auth = await get_access_token()

    headers = {"Content-Type": "application/json", "Authorization": auth}

    params = {"wkc_asset_id": asset_id}
    if container_type == "catalog":
        params["catalog_id"] = container_id
    else:
        params["project_id"] = container_id

    client = get_http_client()

    try:
        response = await client.post(
            settings.di_service_url + DATA_QUALITY_BASE_ENDPOINT + "/search_dq_asset",
            params=params,
            headers=headers,
        )

        dq_id = response.get("id")
        if dq_id:
            return dq_id
        else:
            raise ServiceError(
                f"retrieve_data_quality_id_for_asset failed to find data quality id for asset '{asset_id}' in {container_type} '{container_id}'"
            )
    except ExternalAPIError:
        # This will catch HTTP errors (4xx, 5xx) that were raised by raise_for_status()
        raise
    except Exception as e:
        raise ServiceError(
            f"retrieve_data_quality_id_for_asset failed to find data quality id for asset '{asset_id}' in {container_type} '{container_id}': {str(e)}"
        )


async def retrieve_data_quality(
    data_quality_id: str,
    asset_id: str,
    container_id: str,
    container_type: Literal["project", "catalog"],
) -> DataQuality:
    """
    Retrieve data quality scores for a given data quality asset.

    Args:
        data_quality_id: str: Data quality asset id
        asset_id: str: Asset id
        container_id: str: Container id
        container_type: str: Container type (project or catalog)

    Returns:
        DataQuality: Data quality asset object
    """

    auth = await get_access_token()

    headers = {"Content-Type": "application/json", "Authorization": auth}

    params = {"asset_id": data_quality_id}
    if container_type == "catalog":
        params["catalog_id"] = container_id
    else:
        params["project_id"] = container_id

    client = get_http_client()

    try:
        response = await client.get(
            settings.di_service_url + DATA_QUALITY_BASE_ENDPOINT + "/scores",
            params=params,
            headers=headers,
        )

        scores = [
            score
            for score in response.get("scores", [])
            if score.get("status", "").lower() == "actual"
        ]
        if len(scores) == 0:
            raise ServiceError("Data quality score not found")
        score = scores[0]

        dimension_scores = score.get("dimension_scores", [])

        consistency_list = [
            dimension
            for dimension in dimension_scores
            if dimension["dimension"].get("name", "").lower() == "consistency"
        ]
        consistency = (
            ratio_to_percentage(consistency_list[0]["score"])
            if len(consistency_list) > 0
            else None
        )

        validity_list = [
            dimension
            for dimension in dimension_scores
            if dimension["dimension"].get("name", "").lower() == "validity"
        ]
        validity = (
            ratio_to_percentage(validity_list[0]["score"])
            if len(validity_list) > 0
            else None
        )

        completeness_list = [
            dimension
            for dimension in dimension_scores
            if dimension["dimension"].get("name", "").lower() == "completeness"
        ]
        completeness = (
            ratio_to_percentage(completeness_list[0]["score"])
            if len(completeness_list) > 0
            else None
        )

        base_report_url = (
            f"{settings.ui_url}/data/catalogs/{container_id}/asset/{asset_id}/data-quality"
            if container_type == "catalog"
            else f"{settings.ui_url}/projects/{container_id}/data-assets/{asset_id}/data-quality"
        )
        report_url = append_context_to_url(base_report_url)

        return DataQuality(
            overall=ratio_to_percentage(score["score"]),
            consistency=consistency,
            validity=validity,
            completeness=completeness,
            report_url=report_url,
        )
    except ExternalAPIError:
        # This will catch HTTP errors (4xx, 5xx) that were raised by raise_for_status()
        raise
    except Exception as e:
        raise ServiceError(
            f"retrieve_data_quality_for_asset failed for asset '{asset_id}' in {container_type} '{container_id}': {str(e)}"
        )


def ratio_to_percentage(ratio):
    value = float(ratio)
    percentage = value * 100
    # If the hundredths place (second decimal) is 0, show one decimal
    if int((percentage * 100) % 10) == 0:
        return f"{percentage:.1f}"  # show up to 1 decimal
    else:
        return f"{percentage:.2f}"  # show up to 2 decimals


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
    is_uuid(request.asset_id)
    is_uuid(request.container_id)
    LOGGER.info(
        f"Calling get_data_quality_for_asset with asset_id: {request.asset_id}, "
        f"asset_name: {request.asset_name}, container_id: {request.container_id}, "
        f"container_type: {request.container_type}"
    )

    data_quality_id = await retrieve_data_quality_id_for_asset(
        asset_id=request.asset_id,
        container_id=request.container_id,
        container_type=request.container_type,
    )

    data_quality = await retrieve_data_quality(
        data_quality_id=data_quality_id,
        asset_id=request.asset_id,
        container_id=request.container_id,
        container_type=request.container_type,
    )

    return GetDataQualityForAssetResponse(data_quality=data_quality)


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
