# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Annotated, List

from pydantic import Field
from app.core.registry import service_registry
from app.shared.logging import LOGGER, auto_context

from app.services.profiling.models.create_data_profiles import (
    CreateDataProfilesRequest,
    CreateDataProfilesResponse,
    DataProfileOptions,
)
from app.services.profiling.utils.profiling_common_utils import (
    create_data_profiles as create_data_profiles_util,
)


async def _create_data_profiles(
    request: CreateDataProfilesRequest,
) -> CreateDataProfilesResponse:
    """
    Creates data profiles for specified datasets.
    """
    LOGGER.info(
        "[PROFILING] Creating profiles: catalog=%s, datasets=%s",
        request.catalog_id,
        request.dataset_ids,
    )
    
    return await create_data_profiles_util(
        catalog_id_or_name=request.catalog_id,
        dataset_ids=request.dataset_ids,
        options=request.options,
    )


@service_registry.tool(
    name="create_data_profiles",
    description="""Use this tool when you need to create data profiles for datasets in a catalog. Data profiles analyze data structure, quality, and characteristics to help understand data patterns and identify quality issues.

You can pass either dataset UUIDs or dataset names — names are automatically resolved to IDs.
If you are not sure about the dataset ID, pass the dataset name directly.

Returns: CreateDataProfilesResponse with profile ID, status, and UI URL.

Raises:
    ToolProcessFailedError: If profile creation fails.
    ExternalServiceError: If the profiling service request fails.""",
    tags={"create", "profiling", "metadata_management_and_governance"},
    meta={"version": "1.0", "service": "profiling"},
    annotations={
        "title": "Create Data Profiles for Datasets",
        "destructiveHint": True
    }
)
@auto_context
async def create_data_profiles(
    catalog_id: Annotated[str, Field(description="Catalog ID or name containing the datasets. Examples: 'my-catalog', 'enterprise-catalog-123'")],
    dataset_ids: Annotated[List[str], Field(description="List of dataset UUIDs or dataset names to profile. Names are resolved to IDs automatically. Examples: ['dataset-1', 'ACCOUNT_HOLDERS (1).csv', 'sales-data-2024']")],
    disable_profiling: Annotated[bool, Field(description="If true, skip actual profiling analysis (default: false)")] = False,
    enable_dqa: Annotated[bool, Field(description="If true, enable data quality assessment during profiling (default: false)")] = False,
    bivariate_statistics: Annotated[bool, Field(description="If true, include bivariate statistical analysis (default: false)")] = False,
    enable_fast_classification: Annotated[bool, Field(description="If true, enable fast data classification (default: false)")] = False,
    collect_historical_data: Annotated[bool, Field(description="If true, collect historical profile data (default: true)")] = True,
) -> CreateDataProfilesResponse:
    """
    Wrapper that builds request model and delegates to utility function.
    """
    options = DataProfileOptions(
        disable_profiling=disable_profiling,
        enable_dqa=enable_dqa,
        bivariate_statistics=bivariate_statistics,
        enable_fast_classification=enable_fast_classification,
        collect_historical_data=collect_historical_data,
    )
    
    request = CreateDataProfilesRequest(
        catalog_id=catalog_id,
        dataset_ids=dataset_ids,
        options=options,
    )
    
    return await _create_data_profiles(request)
