# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field, model_validator  # noqa: I001 # Baseline
from app.shared.models import BaseResponseModel
from typing import Any, Dict, List, Optional, Union  # noqa: UP035 # Baseline


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class ExecuteGSQueryRequest(BaseModel):
    gs_query: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description=(
            "The Elasticsearch DSL query body as a JSON string, sent as the request body "
            "to the global search index. "
            "Supports standard ES DSL (e.g. match_all, match, bool) as well as the GS-specific "
            "'gs_user_query' function for full-text and semantic (AI) search. "
            "In gs_user_query: 'search_fields' restricts search to named fields; "
            "'nlq_analyzer_enabled' ignores irrelevant words and prioritises common phrases; "
            "'semantic_search_enabled' (default false) enables LLM-based semantic search — "
            "when true, 'semantic_search_options' may be provided to fine-tune behaviour, "
            "including 'semantic_search_expansion_exclusions' to suppress unwanted semantic expansions "
            "returned in a previous response via 'semantic_search_expansions'. "
            "'semantic_search_expansions' in the response is always empty for lexical (non-semantic) search. "
            'Example (match-all): \'{"query":{"match_all":{}}}\' '
            'Example (lexical GS search): \'{"query":{"gs_user_query":{"search_string":"revenue",'
            '"search_fields":["metadata.name","metadata.description"],'
            '"nlq_analyzer_enabled":true,"nested":false}}}\' '
            'Example (semantic/AI search): \'{"query":{"gs_user_query":{"search_string":"bank",'
            '"semantic_search_enabled":true,"semantic_search_options":'
            '{"semantic_search_expansion_exclusions":{"bank":["repository"]}}}}}\''
        ),
    )
    natural_language_query: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description=(
            "FALLBACK ONLY — use gs_query instead whenever possible. "
            "A plain-English question or search prompt used only when the search intent cannot be expressed "
            "as an Elasticsearch DSL query. When provided (and gs_query is absent), the text-to-query "
            "service automatically generates an ES DSL body from this prompt. "
            "For simple keyword or phrase searches always use gs_query with gs_user_query instead. "
            "Example of when natural_language_query is appropriate: "
            "'Find all customer data assets tagged PII in the Finance catalog'"
        ),
    )
    role: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description=(
            "For governance artifacts limited by zone, limit with this role access. "
            "Allowed values: viewer, editor. Defaults to viewer when omitted."
        ),
    )
    auth_cache: Optional[bool] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Use cached authorization info for building ACL filters. Defaults to false when omitted.",
    )
    auth_scope: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description=(
            "The ACL filters applied to the query. "
            "Allowed values: all, catalog, project, space, category, "
            "ibm_watsonx_governance_catalog, ibm_data_product_catalog, system_scope_data. "
            "Defaults to all when omitted."
        ),
    )
    type: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description=(
            "Index type inside which the document will be searched. "
            "Allowed values: metadata, data, semantic_cache, metadata_vector, "
            "system_metadata_vector_store. Defaults to metadata when omitted."
        ),
    )
    run_as_tenant: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description=("The Tenant ID (BSS Account ID) to run this query as."),
    )

    @model_validator(mode="after")
    def require_query_input(self) -> "ExecuteGSQueryRequest":
        if not self.gs_query and not self.natural_language_query:
            raise ValueError(
                "Either 'gs_query' or 'natural_language_query' must be provided."
            )
        return self


# ---------------------------------------------------------------------------
# Response sub-models — GlobalSearchAdvancedSearchResponse schema
# ---------------------------------------------------------------------------


class GSCamsMetadata(BaseModel):
    """Metadata for a CAMS asset row (GlobalSearchCamsMetadata)."""

    modified_on: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Last modification timestamp (ISO 8601 date-time).",
    )
    created_on: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Creation timestamp (ISO 8601 date-time).",
    )
    artifact_type: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Type of the artifact.",
        examples=["data_asset"],
    )
    name: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Display name of the asset or artifact.",
        examples=["Finance Information"],
    )
    description: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Human-readable description of the asset or artifact.",
        examples=[
            "Details of an individual's financial status, assets, investments, and tax information"
        ],
    )
    modified_by: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="IBMid of the user who last modified the artifact.",
        examples=["IBMid-6780008NLC"],
    )
    steward_ids: Optional[List[str]] = Field(  # noqa: UP006, UP045 # Baseline
        default=None,
        description="IBMids of assigned stewards.",
        examples=[["IBMid-6780008NLC"]],
    )
    state: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Publication state of the artifact.",
        examples=["active"],
    )
    tags: Optional[List[str]] = Field(  # noqa: UP006, UP045 # Baseline
        default=None,
        description="Tags attached to the artifact.",
        examples=[[]],
    )

    model_config = {"extra": "allow"}


class GSCamsRov(BaseModel):
    """Read/ownership/visibility object nested inside GlobalSearchCamsAssets."""

    viewers: Optional[List[str]] = Field(  # noqa: UP006, UP045 # Baseline
        default=None,
        description="List of viewer principals.",
        examples=[[]],
    )
    privacy: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Privacy setting for the asset.",
        examples=["public"],
    )
    owners: Optional[List[str]] = Field(  # noqa: UP006, UP045 # Baseline
        default=None,
        description="List of owner principals.",
        examples=[["IBMid-6780008NLC"]],
    )
    editors: Optional[List[str]] = Field(  # noqa: UP006, UP045 # Baseline
        default=None,
        description="List of editor principals.",
        examples=[[]],
    )

    model_config = {"extra": "allow"}


class GSCamsSourceSystemHistory(BaseModel):
    """Source system history object nested inside GlobalSearchCamsAssets."""

    asset_ids: Optional[List[str]] = Field(  # noqa: UP006, UP045 # Baseline
        default=None,
        description="List of asset IDs from the source system.",
        examples=[[]],
    )
    system_ids: Optional[List[str]] = Field(  # noqa: UP006, UP045 # Baseline
        default=None,
        description="List of system IDs from the source system.",
        examples=[[]],
    )

    model_config = {"extra": "allow"}


class GSCamsAssets(BaseModel):
    """Asset linkage fields inside GlobalSearchCamsEntity (GlobalSearchCamsAssets)."""

    catalog_id: Optional[Union[str, List[str]]] = Field(  # noqa: UP006, UP007, UP045 # Baseline
        default=None,
        description="Catalog identifier. May be a single string or a list of strings.",
        examples=["82b24e89-851c-4085-9912-69b770f68d23"],
    )
    source_system_history: Optional[GSCamsSourceSystemHistory] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Source system history with asset_ids and system_ids.",
    )
    connection_paths: Optional[List[str]] = Field(  # noqa: UP006, UP045 # Baseline
        default=None,
        description="List of connection paths.",
        examples=[[]],
    )
    resource_key: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Human-readable resource key.",
        examples=["Finance Information"],
    )
    rov: Optional[GSCamsRov] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Read/ownership/visibility object (viewers, privacy, owners, editors).",
    )
    column_names: Optional[List[str]] = Field(  # noqa: UP006, UP045 # Baseline
        default=None,
        description="Column names in the asset.",
        examples=[["ID", "NAME", "CITY"]],
    )
    connection_ids: Optional[List[str]] = Field(  # noqa: UP006, UP045 # Baseline
        default=None,
        description="List of connection IDs.",
        examples=[[]],
    )

    model_config = {"extra": "allow"}


class GSCamsEntity(BaseModel):
    """Entity payload for CAMS assets (GlobalSearchCamsEntity)."""

    assets: Optional[GSCamsAssets] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Asset linkage fields.",
    )

    model_config = {"extra": "allow"}


class GSCamsRow(BaseModel):
    """A single result row — GlobalSearchCamsRow."""

    provider_type_id: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Provider type identifier, e.g. 'cams'.",
        examples=["cams"],
    )
    tenant_id: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Tenant identifier.",
        examples=["431900b8-99d1-42eb-bfef-adef2a9aabdb"],
    )
    metadata: Optional[GSCamsMetadata] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Metadata for the CAMS asset.",
    )
    last_updated_at: Optional[int] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Last update time in milliseconds since epoch.",
        examples=[-1551326452],
    )
    artifact_id: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Unique artifact identifier.",
        examples=["653713c4-a154-4dbc-98eb-29f56bf18199"],
    )
    entity: Optional[GSCamsEntity] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Entity payload for the CAMS asset.",
    )
    custom_attributes: Optional[List[Any]] = Field(  # noqa: UP006, UP045 # Baseline
        default=None,
        description="Custom attributes attached to the asset.",
        examples=[[]],
    )
    semantic_search_result: Optional[bool] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Whether this row was produced by semantic (vector) search.",
    )
    score: Optional[float] = Field(  # noqa: UP045 # Baseline
        default=None,
        alias="_score",
        description="Relevance score assigned by the search engine.",
        examples=[801.0],
    )

    model_config = {"extra": "allow", "populate_by_name": True}


# ---------------------------------------------------------------------------
# Semantic search expansion model
# ---------------------------------------------------------------------------


class SemanticSearchExpansion(BaseModel):
    """One entry in the semantic_search_expansions list returned by the API.

    Each entry corresponds to one search term and carries the expansions the
    engine considered plus any exclusions the caller requested.

    Example:
        {
            "search_string": "rugby",
            "expansions": {"rugby": ["football", "sport"]},
            "exclusions": {}
        }
    """

    search_string: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="The original search term this expansion entry relates to.",
        examples=["rugby"],
    )
    expansions: Optional[Dict[str, Any]] = Field(  # noqa: UP006, UP045 # Baseline
        default=None,
        description=(
            "Semantic expansions considered for the search term. "
            "Keys are the original terms; values are lists of semantically equivalent terms."
        ),
        examples=[{"rugby": ["football", "sport"]}],
    )
    exclusions: Optional[Dict[str, Any]] = Field(  # noqa: UP006, UP045 # Baseline
        default=None,
        description=(
            "Expansions explicitly excluded by the caller via "
            "'semantic_search_expansion_exclusions' in the request. "
            "Keys are the original terms; values are lists of excluded equivalent terms."
        ),
        examples=[{}],
    )

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Top-level response model — GlobalSearchAdvancedSearchResponse
# ---------------------------------------------------------------------------


class ExecuteGSQueryResponse(BaseResponseModel):
    """Response for POST /v3/search — GlobalSearchAdvancedSearchResponse."""

    size: int = Field(
        default=0,
        description="Number of rows returned.",
        examples=[1],
    )
    rows: List[GSCamsRow] = Field(  # noqa: UP006 # Baseline
        default_factory=list,
        description="Result items (CAMS) from the global search index.",
    )
    aggregations: Optional[Dict[str, Any]] = Field(  # noqa: UP006, UP045 # Baseline
        default=None,
        description="Aggregation results, if any.",
        examples=[{}],
    )
    semantic_search_expansions: Optional[List[SemanticSearchExpansion]] = Field(  # noqa: UP006, UP045 # Baseline
        default=None,
        description=(
            "Semantic expansion entries returned by the engine, one per search term. "
            "Each entry contains search_string, expansions, and exclusions. "
            "Always empty ([]) for lexical (non-semantic) search."
        ),
        examples=[[{"search_string": "rugby", "expansions": {}, "exclusions": {}}]],
    )
