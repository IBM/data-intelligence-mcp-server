from app.core.registry import service_registry
from app.services.data_product.utils.common_utils import get_dph_catalog_id_for_user
from app.services.data_product.models.get_business_domains import BusinessDomain, GetBusinessDomainsRequest, GetBusinessDomainsResponse
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.logging import LOGGER, auto_context


@service_registry.tool(
    name="data_product_get_business_domains",
    description="""
    This tool gets all business domains listed in the system.
    Use this tool if user is not sure of the business domain name or if the user asks for the list of business domains.
    Example: What are the domains available?
    Call: data_product_get_business_domains with keyword as None.
    Optionally, user can provide a keyword to search for business domains. In this case, call the tool with the keyword.
    Example: What are the domains available for customer data?
    Call: data_product_get_business_domains with keyword as "customer".
    """,
    tags={"sample", "data_product"},
    meta={"version": "1.0", "service": "data_product"}
)
@auto_context
async def get_business_domains(
    request: GetBusinessDomainsRequest
) -> GetBusinessDomainsResponse:
    LOGGER.info(
        f"In the data_product_get_business_domains tool, finding available business domains with keyword {request.keyword}."
    )
    DPH_CATALOG_ID = await get_dph_catalog_id_for_user()
    if not request.keyword:
        search_payload = {"query": "*:*", "sort": "asset.name"}
    else:
        search_payload = {"query": f"asset.name LIKE \"{request.keyword}\""}
    
    response = await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/v2/asset_types/ibm_data_product_domain/search?catalog_id={DPH_CATALOG_ID}&hide_deprecated_response_fields=false",
        json=search_payload,
        tool_name="data_product_attach_business_domain_to_data_product",
    )

    tool_response_list = []
    for domain in response["results"]:
        metadata = domain.get("metadata", {})
        
        tool_response_list.append(
            BusinessDomain(
                id=metadata.get("asset_id", ""),
                name=metadata.get("name", ""),
                description=metadata.get("description", "")
            )
        )

    LOGGER.info(
        f"In the data_product_get_business_domains tool, found {len(tool_response_list)} business domains."
    )
    return GetBusinessDomainsResponse(domains=tool_response_list)


@service_registry.tool(
    name="data_product_get_business_domains",
    description="""
    This tool gets all business domains listed in the system.
    Use this tool if user is not sure of the business domain name or if the user asks for the list of business domains.
    Example: What are the domains available?
    Call: data_product_get_business_domains with keyword as None.
    Optionally, user can provide a keyword to search for business domains. In this case, call the tool with the keyword.
    Example: What are the domains available for customer data?
    Call: data_product_get_business_domains with keyword as "customer".

    Args:
        keyword (str): A keyword to search for business domains. This is an optional field.
    """,
    tags={"sample", "data_product"},
    meta={"version": "1.0", "service": "data_product"}
)
@auto_context
async def wxo_get_business_domains(
    keyword: str | None = None
) -> GetBusinessDomainsResponse:
    """Watsonx Orchestrator compatible version."""

    request = GetBusinessDomainsRequest(
        keyword=keyword
    )

    return await get_business_domains(request)

