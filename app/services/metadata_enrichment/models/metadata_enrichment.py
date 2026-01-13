# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.shared.utils.tool_helper_service import tool_helper_service

BASE_URL = str(tool_helper_service.base_url)
UI_BASE_URL = str(tool_helper_service.ui_base_url)

METADATA_ENRICHMENT_SERVICE_URL = BASE_URL + "/metadata_enrichment/v3"
MDE_START_SELECTIVE_ASSETS_TEMPLATE = (
    METADATA_ENRICHMENT_SERVICE_URL
    + "/metadata_enrichment_assets/${mde_id}/start_selective_enrichment"
)
CAMS_ASSET_BASE_URL = BASE_URL + "/v2/assets"
JOBS_BASE_URL = BASE_URL + "/v2/jobs"
MDE_UI_DISPLAY_URL = UI_BASE_URL + "/gov/metadata-enrichments/display"
MDE_UI_URL_TEMPLATE = (
    MDE_UI_DISPLAY_URL
    + "/${mde_id}/structured/columns?project_id=${project_id}&context=df"
)


class MetadataEnrichmentCreationRequest(BaseModel):
    """
    Unified request model for creating or updating metadata enrichment assets.
    
    The tool automatically detects whether to create or update based on whether
    an MDE with the given name exists in the project:
    - If MDE exists: UPDATE mode (updates existing)
    - If MDE doesn't exist: CREATE mode (creates new)
    """
    project_name: str = Field(
        ..., description="The name of the project."
    )
    metadata_enrichment_name: str = Field(
        ..., description="The name of the metadata enrichment asset. Used to find existing MDE (for update) or as the name for new MDE (for create)."
    )
    objective_names: list[str] | str = Field(
        ...,
        description="""List of names of objectives for the enrichment job.
        Supported objectives are 'profile', 'dq_gen_constraints', 'analyze_quality', 'assign_terms', 'analyze_relationships', 'dq_sla_assessment', and 'semantic_expansion'.
        Required for both create and update modes.""",
    )
    category_names: Optional[list[str] | str] = Field(
        None,
        description="""Category names for governance scope.
        - CREATE mode: Required (must be provided)
        - UPDATE mode: Optional (only updates if provided)""",
    )
    dataset_names: Optional[list[str] | str] = Field(
        None,
        description="""Dataset names to include in the metadata enrichment asset.
        - CREATE mode: Required (must be provided)
        - UPDATE mode: Ignored with warning (datasets cannot be modified after creation)""",
    )
    description: Optional[str] = Field(
        None,
        description="Description of the metadata enrichment asset. Used in both create and update modes."
    )
    new_name: Optional[str] = Field(
        None,
        description="New name for the metadata enrichment asset. Only used in UPDATE mode to rename the MDE. Ignored in CREATE mode."
    )

class PatchMetadataEnrichmentRequest(BaseModel):
    project_name: str = Field(
        ..., description="The name of the project containing the metadata enrichment asset."
    )
    metadata_enrichment_name: str = Field(
        ..., description="The name of the metadata enrichment asset to patch."
    )
    objective_names: list[str] | str = Field(
        ...,
        description="""List of names of objectives to set for the enrichment job.
        Supported objectives are 'profile', 'dq_gen_constraints', 'analyze_quality',
        and 'semantic_expansion'. These will replace the existing objectives.""",
    )
    category_names: Optional[list[str] | str] = Field(
        None,
        description="""Optional list of category names to update the governance scope.
        If provided, these will replace the existing categories.""",
    )


class MetadataEnrichmentExecutionRequest(BaseModel):
    project_name: str = Field(
        ..., description="The name of the project you want to execute a metadata enrichment."
    )
    metadata_enrichment_name: str = Field(
        ..., description="The name of the metadata enrichment you want to execute."
    )
    dataset_names: Optional[list[str] | str] = Field(
        None,
        description="Dataset names of the specified datasets to be enriched with metadata."
    )


class MetadataEnrichmentAnalysisRequest(BaseModel):
    project_name: str = Field(
        ..., description="The name of the project for which the analysis is to be performed."
    )
    dataset_names: list[str] | str = Field(
        ..., description="Dataset names of the specified datasets to be enriched with metadata."
    )
    category_names: list[str] | str = Field(
        ...,
        description="""Names of the categories for which data quality analysis is required.
        If a single category name is provided, it should be a string. If multiple categories are specified,
        they should be provided as a list of strings.""",
    )


class MetadataEnrichmentObjective(str, Enum):
    PROFILE = "profile"
    DQ_GEN_CONSTRAINTS = "dq_gen_constraints"
    ANALYZE_QUALITY = "analyze_quality"
    SEMANTIC_EXPANSION = "semantic_expansion"
    ASSIGN_TERMS = "assign_terms"
    ANALYZE_RELATIONSHIPS = "analyze_relationships"
    DQ_SLA_ASSESSMENT = "dq_sla_assessment"


class MetadataEnrichmentAssetEnrichmentJob(BaseModel):
    name: str = Field(description="The name of the metadata enrichment job.")


class ContainerAssets(BaseModel):
    metadata_imports: Optional[list[str]] = Field(
        None,
        description="A list of metadata import asset identifiers to add to a new metadata enrichment asset.",
    )


class MetadataEnrichmentAssetDataScope(BaseModel):
    enrichment_assets: Optional[list[str]] = Field(
        None,
        description="A list of data asset identifiers to add to a new Metadata Enrichment Asset.",
    )
    container_assets: Optional[ContainerAssets] = Field(
        None,
        description="A set of containers containing assets. Currently, only containers of type metadata import asset are supported.",
    )


class EnrichmentOptionsStructured(BaseModel):
    profile: bool = Field(
        False,
        description="Flag that indicates whether data profiling should be executed.",
    )
    assign_terms: bool = Field(
        False,
        description="Flag that indicates whether term assignment should be executed.",
    )
    analyze_quality: bool = Field(
        False,
        description="Flag that indicates whether data quality analysis should be executed.",
    )
    analyze_relationships: bool = Field(
        False,
        description="Flag that indicates whether primary key analysis should be executed.",
    )
    semantic_expansion: bool = Field(
        False,
        description="Flag that indicates whether semantic expansion should be executed.",
    )
    data_search: bool = Field(
        False,
        description="Flag that indicates whether data search should be executed.",
    )
    dq_sla_assessment: bool = Field(
        False,
        description="Flag that indicates whether service level agreement assessments should be executed.",
    )
    dq_gen_constraints: bool = Field(
        False,
        description="Flag that indicates whether data quality constraints should be generated or not.",
    )


class EnrichmentOptions(BaseModel):
    structured: EnrichmentOptionsStructured = Field(
        EnrichmentOptionsStructured(),
        description="Enrichment options for structured data.",
    )


class GovernanceScopeCategoryTypeEnum(str, Enum):
    CATEGORY = "category"


class GovernanceScopeCategory(BaseModel):
    id: str = Field(description="Identifier of the category.")
    type: GovernanceScopeCategoryTypeEnum = Field(
        GovernanceScopeCategoryTypeEnum.CATEGORY,
        description="A category used in a metadata enrichment asset's governance scope.",
    )


class SamplingMethodEnum(str, Enum):
    RANDOM = "random"
    TOP = "top"


class SamplingAnalysisMethodEnum(str, Enum):
    FIXED = "fixed"
    PERCENTAGE = "percentage"


class SamplingStructuredSampleSizeOptions(BaseModel):
    row_number: int = Field(
        description="The maximum number of rows to profile. A missing or zero value indicates that the full set of rows must be profiled."
    )
    classify_value_number: int = Field(
        100,
        description="The maximum size of the various distributions produced by the profiling process. A zero value is mapped to the default value.",
    )


class SamplingStructuredSampleSizePercentageOptions(BaseModel):
    decimal_value: float = Field(
        description="The sample percentage expressed as decimal value."
    )
    row_number_min: int = Field(description="The minimum number of rows to profile.")
    row_number_max: int = Field(
        description="The maximum number of rows to profile. A missing or zero value indicates that the full set of rows must be profiled."
    )
    classify_value_number: int = Field(
        100,
        description="The maximum size of the various distributions produced by the profiling process.",
    )


class SamplingStructuredSampleSize(BaseModel):
    name: Optional[str] = Field(
        None, description="An optional name for the sample size configuration."
    )
    options: Optional[SamplingStructuredSampleSizeOptions] = Field(
        None,
        description="Sample size options for structured data assets of a metadata enrichment asset. Required if sampling method is 'fixed'.",
    )
    percentage_options: Optional[SamplingStructuredSampleSizePercentageOptions] = Field(
        None,
        description="Initial sample size percentage options for structured data assets in a metadata enrichment asset. Required if sampling method is 'percentage'.",
    )


class SamplingStructured(BaseModel):
    method: SamplingMethodEnum = Field(description="The sampling method.")
    analysis_method: SamplingAnalysisMethodEnum = Field(
        SamplingAnalysisMethodEnum.FIXED, description="The sampling analysis method."
    )
    sample_size: SamplingStructuredSampleSize = Field(
        description="Initial metadata enrichment asset sample size for structured data assets."
    )


class Sampling(BaseModel):
    structured: SamplingStructured = Field(
        SamplingStructured(
            method=SamplingMethodEnum.TOP,
            analysis_method=SamplingAnalysisMethodEnum.FIXED,
            sample_size=SamplingStructuredSampleSize(
                options=SamplingStructuredSampleSizeOptions(
                    row_number=1000, classify_value_number=100
                )
            ),
        ),
        description="Initialization information for metadata enrichment asset sampling options for structured data assets.",
    )


class DatascopeOfRerunsEnum(str, Enum):
    ALL = "all"
    DELTA = "delta"


class SuggestedDataQualityCheck(BaseModel):
    id: str = Field(..., description="The id of the suggested data quality check.")
    enabled: bool = Field(
        ...,
        description="The flag whether the suggested data quality check is enabled or not.",
    )


class QualityOrigins(BaseModel):
    profiling: bool = Field(
        ...,
        description="Flag that indicates whether data profiling should be executed.",
    )
    business_terms: bool = Field(
        ...,
        description="Flag that indicates whether business terms should be used for data quality checks.",
    )
    relationships: bool = Field(
        ...,
        description="Flag that indicates whether relationships should be used for data quality checks.",
    )


class DataQualityStructured(BaseModel):
    dq_checks_suggested: list[SuggestedDataQualityCheck] = Field(
        [],
        description="List of suggested Data Quality Checks. Each DQCheck consists of 2 fields id and a flag whether it is enabled or not.",
    )
    quality_origins: QualityOrigins = Field(
        QualityOrigins(profiling=True, business_terms=False, relationships=False),
        description="Options that allow to define on which sources suggestions for data quality checks should be based.",
    )


class DataQuality(BaseModel):
    structured: DataQualityStructured = Field(
        DataQualityStructured(),
        description="Initialization information for the data quality objectives for structured data assets in a metadata enrichment.",
    )


class MetadataEnrichmentAssetObjective(BaseModel):
    enrichment_options: EnrichmentOptions = Field(
        EnrichmentOptions(),
        description="Enrichment options of metadata enrichment asset.",
    )
    governance_scope: list[GovernanceScopeCategory] = Field(
        [], description="A list of categories to be used for metadata enrichment."
    )
    sampling: Sampling = Field(
        Sampling(),
        description="Initialization information for the metadata enrichment asset sampling options.",
    )
    datascope_of_reruns: DatascopeOfRerunsEnum = Field(
        DatascopeOfRerunsEnum.ALL,
        description="The type of data scope to be used in metadata enrichment job reruns after the initial full enrichment.",
    )
    data_quality: DataQuality = Field(
        DataQuality(),
        description="Initialization information for the data quality objectives for metadata Enrichment",
    )


class MetadataEnrichmentAsset(BaseModel):
    name: str = Field(
        description="The name of the metadata enrichment asset to be created."
    )
    job: MetadataEnrichmentAssetEnrichmentJob = Field(
        description="Initialization information for the metadata enrichment asset enrichment job"
    )
    data_scope: MetadataEnrichmentAssetDataScope = Field(
        MetadataEnrichmentAssetDataScope(),
        description="Initialization information for a metadata enrichment asset's data scope definition.",
    )
    objective: MetadataEnrichmentAssetObjective = Field(
        MetadataEnrichmentAssetObjective(),
        description="Initialization information for metadata enrichment asset objectives.",
    )

    def __init__(self, name: str):
        super().__init__(name=name, job=MetadataEnrichmentAssetEnrichmentJob(name=name))


class OperationStatusEnum(str, Enum):
    ACCEPTED = "accepted"
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"
    CANCELED = "canceled"
    SUCCEEDED = "succeeded"
    SUCCEEDED_WITH_ERRORS = "succeeded_with_errors"


class DataScopeOperation(BaseModel):
    id: str = Field(description="The unique identifier of this resource.")
    status: OperationStatusEnum = Field(
        description="Status of a metadata enrichment asset operation."
    )
    target_resource_id: Optional[str] = Field(
        None, description="The identifier of the target resource."
    )
    target_resource_location: Optional[str] = Field(
        None, description="The target resource location."
    )


class MetadataEnrichmentAssetObjectivePatch(BaseModel):
    enrichment_options: EnrichmentOptions = Field(
        EnrichmentOptions(),
        description="Patch for the enrichment options of a metadata enrichment asset.",
    )
    governance_scope: list[GovernanceScopeCategory] = Field(
        [], description="A list of categories to be used for metadata enrichment."
    )


class MetadataEnrichmentAssetPatch(BaseModel):
    objective: MetadataEnrichmentAssetObjectivePatch = Field(
        MetadataEnrichmentAssetObjectivePatch(),
        description="Objective patch of a metadata enrichment asset.",
    )


class DataScopeAssetSelection(BaseModel):
    ids: list[str] = Field(..., description="A list of data asset identifiers.")


class MetadataEnrichmentAssetDataScopeUpdateRequest(BaseModel):
    assets_to_add: DataScopeAssetSelection = Field(
        ..., description="A subset of assets in a metadata enrichment asset."
    )


class MetadataEnrichmentAssetPatchResponse(BaseModel):
    id: str = Field(..., description="The unique identifier of this resource.")
    name: str = Field(..., description="The name of the metadata enrichment asset.")


class MetadataEnrichmentRun(BaseModel):
    metadata_enrichment_id: str = Field(
        ..., description="The unique identifier of the parent metadata enrichment."
    )
    job_id: str = Field(
        ..., description="The unique identifier of the metadata enrichment job."
    )
    job_run_id: str = Field(
        ..., description="The unique identifier of the metadata enrichment job run."
    )
    project_id: str = Field(..., description="The unique identifier of the project.")
    metadata_enrichment_ui_url: str = Field(
        ..., description="The URL to the metadata enrichment asset in the UI."
    )


class MetadataEnrichmentAssetInfo(BaseModel):
    metadata_enrichment_id: str = Field(
        ..., description="The unique identifier of the parent metadata enrichment."
    )
    dataset_ids: list[str] = Field(..., description="The list of dataset identifiers.")
