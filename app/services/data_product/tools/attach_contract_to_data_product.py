# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Optional
from app.core.registry import service_registry
from app.services.data_product.models.attach_contract_to_data_product import (
    AttachURLContractToDataProductRequest,
    GetContractTemplateResponse,
    ContractTemplate,
    AttachContractTemplateToDataProductRequest,
    CreateAndAttachCustomContractRequest,
)
from app.services.data_product.utils.common_utils import add_catalog_id_suffix
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.logging import LOGGER, auto_context


@service_registry.tool(
    name="data_product_attach_url_contract_to_data_product",
    description="""
    This tool attaches the given URL contract to a data product draft.
    Appropriate success message is sent if the URL contract is attached to the data product draft.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@add_catalog_id_suffix(field_name="data_product_draft_id")
@add_catalog_id_suffix(field_name="contract_terms_id")
@auto_context
async def attach_url_contract_to_data_product(
    request: AttachURLContractToDataProductRequest,
) -> str:
    LOGGER.info(
        f"In the data_product_attach_url_contract_to_data_product tool, attaching URL contract {request.contract_url} with name {request.contract_name} to the data product draft {request.data_product_draft_id}."
    )
    
    # step 1: attach the URL contract to data product draft
    payload = {
        "url": request.contract_url,
        "type": "terms_and_conditions",
        "name": request.contract_name,
    }
    
    await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{request.data_product_draft_id}/contract_terms/{request.contract_terms_id}/documents",
        json=payload,
        tool_name="data_product_attach_url_contract_to_data_product",
    )
    
    LOGGER.info(
        f"In the data_product_attach_url_contract_to_data_product tool, attached URL contract {request.contract_url} with name {request.contract_name} to the data product draft {request.data_product_draft_id}."
    )
    return f"Attached URL contract {request.contract_url} with name {request.contract_name} to the data product draft {request.data_product_draft_id}."


@service_registry.tool(
    name="data_product_attach_url_contract_to_data_product",
    description="""
    This tool attaches the given URL contract to a data product draft.
    Appropriate success message is sent if the URL contract is attached to the data product draft.
    
    Args:
        contract_url (str): The URL of the contract.
        contract_name (str): The name of the contract.
        contract_terms_id (str): The ID of the contract terms asset. This should be fetched from the context (not from the user).
        data_product_draft_id (str): The ID of the data product draft to which the contract is to be attached.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
async def wxo_attach_url_contract_to_data_product(
    contract_url: str,
    contract_name: str,
    contract_terms_id: str,
    data_product_draft_id: str
) -> str:
    """Watsonx Orchestrator compatible version that expands AttachURLContractToDataProductRequest object into individual parameters."""

    request = AttachURLContractToDataProductRequest(
        contract_url=contract_url,
        contract_name=contract_name,
        contract_terms_id=contract_terms_id,
        data_product_draft_id=data_product_draft_id
    )

    # Call the original attach_url_contract_to_data_product function
    return await attach_url_contract_to_data_product(request)


@service_registry.tool(
    name="data_product_get_contract_templates",
    description="""
    This tool gets all contract templates defined in the system.
    This is sometimes called before calling `data_product_attach_contract_template_to_data_product` tool.
    Example 1: Add contract1 template to the draft
         - This will first call `data_product_get_contract_templates` to get the list of contract templates (if contract template ID is not known) and passes the contract template ID of contract1 to the next tool `data_product_attach_contract_template_to_data_product`.
    Example 2: What are my contract templates?
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def get_contract_templates()-> GetContractTemplateResponse:
    LOGGER.info("In data_product_get_contract_templates, getting all contract templates.")
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/contract_templates",
        tool_name="data_product_get_contract_templates",
    )
    contract_templates = [
        ContractTemplate(
            contract_template_id=contract_template.get("id"),
            contract_template_name=contract_template.get("name"),
        )
        for contract_template in response.get("contract_templates", [])
    ] 
    LOGGER.info(f"In data_product_get_contract_templates, found {len(contract_templates)} contract templates.")
    return GetContractTemplateResponse(contract_templates=contract_templates)


@service_registry.tool(
    name="data_product_get_contract_templates",
    description="""
    This tool gets all contract templates defined in the system.
    This is sometimes called before calling `data_product_attach_contract_template_to_data_product` tool.
    Example 1: Add contract1 template to the draft
         - This will first call `data_product_get_contract_templates` to get the list of contract templates (if contract template ID is not known) and passes the contract template ID of contract1 to the next tool `data_product_attach_contract_template_to_data_product`.
    Example 2: What are my contract templates?
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
async def wxo_get_contract_templates()-> GetContractTemplateResponse:
    return await get_contract_templates()

def deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge two dictionaries. Values from override will be merged into base.
    For nested dictionaries, this function recursively merges them.
    For lists and other types, override values replace base values.
    
    Args:
        base: The base dictionary (template defaults)
        override: The override dictionary (user-provided values)
    
    Returns:
        A new dictionary with merged values
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = deep_merge(result[key], value)
        else:
            # For non-dict values (including lists), override replaces base
            result[key] = value
    
    return result


def get_full_contract_terms_empty_values() -> dict:
    return {
        "documents":[
            
        ],
        "overview":{
            "api_version":None,
            "kind": None,
            "name": None,
            "version": None,
            "domain":{
                "id": None,
                "name": None
            }
        },
        "description":{
            "purpose": None,
            "limitations": None,
            "usage": None,
            "more_info":[
                {
                    "type": None,
                    "url": None
                }
            ]
        },
        "organization":[
            {
                "user_id": None,
                "role": None
            }
        ],
        "price":{
            "amount": None,
            "currency": None,
            "unit": None
        },
        "sla":[
            {
                "default_element": None,
                "properties":[
                {
                    "property": None,
                    "value": None
                },
                {
                    "property": None,
                    "value": None
                }
            ]
        }
    ],
    "support_and_communication":[
        {
            "channel": None,
            "url": None
        }
    ],
    "custom_properties":[
        {
            "key": None,
            "value": None
        }
    ]
    }

@service_registry.tool(
    name="data_product_attach_contract_template_to_data_product",
    description="""
    This tool attaches the selected contract template to data product draft.
    Call `data_product_get_contract_templates` tool before calling this tool, if you don't know the ID of the contract template.
    Also, it is a good idea to list all contract templates to user so the user can choose from the list.
    
    The tool works in two steps:
    1. First call: Do NOT provide contract_terms parameter (or set to None). This fetches and displays the contract template's default values to the user for review.
    2. Second call: Provide contract_terms parameter:
       - To use template defaults as-is: set contract_terms={} (empty dict)
       - To customize: set contract_terms with user's custom values following the exact schema structure from first call
    
    IMPORTANT: contract_terms must follow the exact nested structure shown in the first call's output.
    The first call displays the complete schema with all available fields.
    
    Example workflow:
         - Call `data_product_get_contract_templates` to get the list of contract templates.
         - Call this tool WITHOUT contract_terms parameter to see the default values and complete schema (first call)
         - User reviews the schema structure and decides:
           * To use defaults: call again with contract_terms={} (empty dict).
           * To customize: call again with contract_terms following the exact schema structure.
    
    Example customizations (must match schema structure):
         - Update description limitations: {"description": {"limitations": "unlimited"}}
         - Add SLA with properties: {"sla": [{"properties": [{"property": "property1", "value": "value1"}, {"property": "property2", "value": "value2"}]}]}
         - Add custom properties: {"custom_properties": [{"key": "refresh", "value": "daily"}, {"key": "relevancy", "value": "new"}]}
         - Update overview name: {"overview": {"name": "My Custom Contract"}}
         - Combine multiple: {"description": {"limitations": "unlimited"}, "custom_properties": [{"key": "refresh", "value": "daily"}]}
    
    The deep_merge preserves all template defaults while applying your customizations.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def attach_contract_template_to_data_product(
    request: AttachContractTemplateToDataProductRequest
)-> str:
    LOGGER.info(f"In data_product_attach_contract_template_to_data_product, attaching contract template {request.contract_template_id} to data product draft {request.data_product_draft_id} with contract terms {request.contract_terms_id}")
    
    # Fetch the contract template to get the default contract_terms
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/contract_templates/{request.contract_template_id}",
        tool_name="data_product_attach_contract_template_to_data_product",
    )
    template_contract_terms = response.get("contract_terms", {})
    
    LOGGER.info(f"Contract template default values: {template_contract_terms}")

    full_contract_terms_empty_values = get_full_contract_terms_empty_values()
    
    # If contract_terms is not provided, this is the first call - display the contract terms for review
    if request.contract_terms is None:
        # Merge full_contract_terms_empty_values (complete schema) with template_contract_terms (actual values) so LLM knows:
        # 1. The complete structure/format of all possible contract fields
        # 2. The actual values from this specific template
        # This helps LLM correctly format contract_terms when adding new fields or updating existing ones
        merged_contract_terms = deep_merge(full_contract_terms_empty_values, template_contract_terms)
        LOGGER.info(f"merged_contract_terms: {merged_contract_terms}")
        result_message = f"Retrieved contract template '{request.contract_template_id}' with the following contract terms:\n\n"
        result_message += f"{merged_contract_terms}\n\n"
        result_message += "Please review these values. To proceed, call this tool again with contract_terms:\n"
        result_message += "- To use template defaults as-is: set contract_terms={}\n"
        result_message += "- To customize: contract_terms={\"field1\": \"value1\", ...}\n\n"
        result_message += "IMPORTANT: When providing contract_terms, you must follow the exact nested structure shown above.\n"
        result_message += "For example, to update the name in overview, use: {\"overview\": {\"name\": \"My Custom Name\"}}\n"
        result_message += "The deep_merge function will combine your values with the template defaults.\n"
        result_message += "You can override existing fields or add new information to empty fields following the structure shown above."
        return result_message
    
    # User has provided contract_terms (even if empty dict) - proceed with attachment
    # Always deep merge: empty dict uses all defaults, provided values override/extend defaults
    LOGGER.info(f"Deep merging user-provided contract terms with template defaults. User provided: {request.contract_terms}")
    contract_terms = deep_merge(template_contract_terms, request.contract_terms or {})
    LOGGER.info(f"Final contract terms after deep merge: {contract_terms}")
    
    await tool_helper_service.execute_put_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{request.data_product_draft_id}/contract_terms/{request.contract_terms_id}",
        json=contract_terms,
        tool_name="data_product_attach_contract_template_to_data_product",
    )
    LOGGER.info(
        f"In the data_product_attach_contract_template_to_data_product tool, attached contract template {request.contract_template_id} to the data product draft {request.data_product_draft_id}."
    )
    
    # Return a message that includes confirmation of attachment
    if not request.contract_terms:
        result_message = f"Successfully attached contract template {request.contract_template_id} to the data product draft {request.data_product_draft_id} using template default values."
    else:
        result_message = f"Successfully attached contract template {request.contract_template_id} to the data product draft {request.data_product_draft_id}. "
        result_message += f"Custom values were applied for the following fields: {list(request.contract_terms.keys())}"
    
    return result_message

@service_registry.tool(
    name="data_product_attach_contract_template_to_data_product",
    description="""
    This tool attaches the selected contract template to data product draft.
    Call `data_product_get_contract_templates` tool before calling this tool, if you don't know the ID of the contract template.
    Also, it is a good idea to list all contract templates to user so the user can choose from the list.
    
    The tool works in two steps:
    1. First call: Do NOT provide contract_terms parameter (or set to None). This fetches and displays the contract template's default values to the user for review.
    2. Second call: Provide contract_terms parameter:
       - To use template defaults as-is: set contract_terms={} (empty dict)
       - To customize: set contract_terms with user's custom values following the exact schema structure from first call
    
    IMPORTANT: contract_terms must follow the exact nested structure shown in the first call's output.
    The first call displays the complete schema with all available fields.
    
    Example workflow:
         - Call `data_product_get_contract_templates` to get the list of contract templates.
         - Call this tool WITHOUT contract_terms parameter to see the default values and complete schema (first call)
         - User reviews the schema structure and decides:
           * To use defaults: call again with contract_terms={} (empty dict).
           * To customize: call again with contract_terms following the exact schema structure.
    
    Example customizations (must match schema structure):
         - Update description limitations: {"description": {"limitations": "unlimited"}}
         - Add SLA with properties: {"sla": [{"properties": [{"property": "property1", "value": "value1"}, {"property": "property2", "value": "value2"}]}]}
         - Add custom properties: {"custom_properties": [{"key": "refresh", "value": "daily"}, {"key": "relevancy", "value": "new"}]}
         - Update overview name: {"overview": {"name": "My Custom Contract"}}
         - Combine multiple: {"description": {"limitations": "unlimited"}, "custom_properties": [{"key": "refresh", "value": "daily"}]}
    
    The deep_merge preserves all template defaults while applying your customizations.
    
    Args:
        contract_template_id (str): The ID of the contract template.
        data_product_draft_id (str): The ID of the data product draft.
        contract_terms_id (str): The ID of the contract terms asset.
        contract_terms (dict, optional): Optional contract terms values to customize the template. If None, displays template defaults for review (first call). If empty dict {}, uses template defaults and attaches (second call). If provided with values, deep merges with template defaults and attaches. Must follow the schema structure shown in first call.
    Returns:
        str: The message indicating the success of the operation or displaying contract terms for review.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
async def wxo_attach_contract_template_to_data_product(
    contract_template_id: str,
    data_product_draft_id: str,
    contract_terms_id: str,
    contract_terms: Optional[dict] = None
)-> str:
    request = AttachContractTemplateToDataProductRequest(
        contract_template_id=contract_template_id,
        data_product_draft_id=data_product_draft_id,
        contract_terms_id=contract_terms_id,
        contract_terms=contract_terms
    )

    # Call the original attach_contract_template_to_data_product function
    return await attach_contract_template_to_data_product(request)



@service_registry.tool(
    name="data_product_create_and_attach_custom_contract",
    description="""
    This tool creates a custom contract from scratch and attaches it to a data product draft.
    Unlike the template-based tool, this does not use any predefined template. Instead, it allows
    users to create a completely custom contract by providing their own values.
    
    The tool works in two steps:
    1. First call: Do NOT provide contract_terms parameter (or set to None). This displays the empty contract schema to show all available fields.
    2. Second call: Provide contract_terms parameter with user's custom values to create and attach the contract.
    
    IMPORTANT: contract_terms must follow the exact nested structure shown in the first call's output.
    The first call displays the complete schema with all available fields.
    
    Example workflow:
         - Call this tool WITHOUT contract_terms parameter to see the empty schema
         - User reviews the schema structure
         - Call this tool again WITH contract_terms={...} containing values (following the exact schema structure)
         - The contract is created and attached to the data product draft
    
    Note: Not all fields are mandatory. Users only need to provide values for the fields they want to include.
    Empty dict is not allowed - custom contracts must have at least some values.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def create_and_attach_custom_contract(
    request: CreateAndAttachCustomContractRequest
) -> str:
    LOGGER.info(f"In data_product_create_and_attach_custom_contract, creating custom contract for data product draft {request.data_product_draft_id} with contract terms {request.contract_terms_id}")
    
    # Get the full empty contract terms schema
    full_contract_terms_empty_values = get_full_contract_terms_empty_values()
    
    # If contract_terms is not provided, this is the first call - display the empty schema
    if request.contract_terms is None:
        LOGGER.info("Displaying empty contract schema to user")
        result_message = "Here is the contract schema with all available fields:\n\n"
        result_message += f"{full_contract_terms_empty_values}\n\n"
        result_message += "Please review the schema and provide values for the fields you want to include in your custom contract.\n"
        result_message += "Note: Not all fields are mandatory. Only provide values for the fields you need.\n\n"
        result_message += "IMPORTANT: When providing contract_terms, you must follow the exact nested structure shown above.\n"
        result_message += "For example, to set the name in overview, use: {\"overview\": {\"name\": \"My Product\"}}\n"
        result_message += "The deep_merge function will combine your values with the schema structure.\n\n"
        result_message += "To proceed:\n"
        result_message += "- Call this tool again WITH contract_terms={...} containing your values (following the structure above)"
        return result_message
    
    # User has provided contract_terms - validate it's not empty
    if not request.contract_terms:
        return "Empty custom contract is not allowed. Please provide contract_terms with at least some values following the schema structure shown in the first call."
    
    # Merge user-provided values with the empty schema
    # This ensures we have the complete structure while only including user-provided values
    LOGGER.info("Merging user-provided contract terms with empty schema")
    contract_terms = deep_merge(full_contract_terms_empty_values, request.contract_terms)
    LOGGER.info(f"Final contract terms: {contract_terms}")
    
    # Attach the custom contract to the data product draft
    await tool_helper_service.execute_put_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{request.data_product_draft_id}/contract_terms/{request.contract_terms_id}",
        json=contract_terms,
        tool_name="data_product_create_and_attach_custom_contract",
    )
    LOGGER.info(
        f"In the data_product_create_and_attach_custom_contract tool, created and attached custom contract to the data product draft {request.data_product_draft_id}."
    )
    
    # Return success message
    result_message = f"Successfully created and attached custom contract to the data product draft {request.data_product_draft_id}. "
    result_message += f"Contract includes values for the following fields: {list(request.contract_terms.keys())}"
    
    return result_message


@service_registry.tool(
    name="data_product_create_and_attach_custom_contract",
    description="""
    This tool creates a custom contract from scratch and attaches it to a data product draft.
    Unlike the template-based tool, this does not use any predefined template. Instead, it allows
    users to create a completely custom contract by providing their own values.
    
    The tool works in two steps:
    1. First call: Do NOT provide contract_terms parameter (or set to None). This displays the empty contract schema to show all available fields.
    2. Second call: Provide contract_terms parameter with user's custom values to create and attach the contract.
    
    IMPORTANT: contract_terms must follow the exact nested structure shown in the first call's output.
    The first call displays the complete schema with all available fields.
    
    Example workflow:
         - Call this tool WITHOUT contract_terms parameter to see the empty schema
         - User reviews the schema structure
         - Call this tool again WITH contract_terms={...} containing values (following the exact schema structure)
         - The contract is created and attached to the data product draft
    
    Note: Not all fields are mandatory. Users only need to provide values for the fields they want to include.
    Empty dict is not allowed - custom contracts must have at least some values.
    
    Args:
        data_product_draft_id (str): The ID of the data product draft.
        contract_terms_id (str): The ID of the contract terms asset.
        contract_terms (dict, optional): Custom contract terms values to create and attach to the data product. Must follow the exact nested structure from the schema. If None, the empty schema will be shown. If provided with values, the contract will be created and attached (empty dict not allowed for custom contracts).
    Returns:
        str: The message indicating the success of the operation or displaying the schema for review.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
async def wxo_create_and_attach_custom_contract(
    data_product_draft_id: str,
    contract_terms_id: str,
    contract_terms: Optional[dict] = None
) -> str:
    request = CreateAndAttachCustomContractRequest(
        data_product_draft_id=data_product_draft_id,
        contract_terms_id=contract_terms_id,
        contract_terms=contract_terms
    )

    # Call the original create_and_attach_custom_contract function
    return await create_and_attach_custom_contract(request)
