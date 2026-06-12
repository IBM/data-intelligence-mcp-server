# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
# This file has been modified with the assistance of IBM Bob AI tool

from app.core.registry import service_registry
from app.services.data_protection_rules.models.create_rule import (
    CreateRuleRequest,
    CreateRuleResponse,
)
from app.core.settings import settings, ENV_MODE_SAAS
from app.services.data_protection_rules.utils.create_rule_util import (
    create_rule_from_payload,
    get_json_to_data_protect_rule,
)
from app.shared.logging.generate_context import auto_context
from app.shared.logging import LOGGER
from app.shared.exceptions.base import ExternalAPIError
from app.shared.utils.tool_helper_service import tool_helper_service
# Message templates for natural language rule creation
REFER_OBJECT_MESSAGE_TEMPLATE = (
    "To create a data protection rule, a referenced object in your request has some issues.\n"
    "**Reason:**\n {error_message}\n"
)

WRONG_RULE_FORMAT_MESSAGE_TEMPLATE = (
    "**User input**: {user_input}, \n"
    "Since your request couldn't be automatically converted into a valid data protection rule format, you'll need to define it more precisely. \n"
    "**Example Rule Patterns:** \n"
    "1. **Mask sensitive data:**  \n"
    "Mask the CreditCardNumber column in the customer_transactions table for all users except those in the Fraud Analysts user group.\n "
    "2. **Restrict access:** \n"
    "Deny access to any data assets classified as Personally Identifiable Information in the employee_db schema for users who are not members of the HR_Managers user group. \n"
    "3. **Filter data:**  \n"
    "Filter rows from the loan_applications table where the credit_score column is below 600 whenever the user belongs to the ExternalPartners group. \n"
    "\nPlease specify which type of rule you need and provide the exact details including:\n"
    "- Table/schema name. \n"
    "- Column name to protect. \n"
    "- User groups, User name or Tag to include/exclude. \n"
    "- Support governance artifacts: Data class, Business term, Classification. \n"
    "- Specific protection action (mask column, deny access, filter rows, obfuscate column, substitute column.)")

RULE_CREATION_DESCRIPTION = """Create a data protection rule from JSON string.

⚠️ IMPORTANT: Call get_data_protection_rule_schema() FIRST to get the JSON format, valid terms, and examples.

This tool accepts a JSON string defining the rule and creates it in the system.

WORKFLOW:
1. FIRST: Call get_data_protection_rule_schema() to understand the JSON format
2. THEN: Call this tool with preview_only=true (default) to preview the rule
3. FINALLY: After user confirms, call again with preview_only=false to create

Args:
    rule_json: JSON string defining the rule (get format from get_data_protection_rule_schema())
    preview_only: If true (default), shows preview. If false, creates the rule.

Returns:
    Preview or creation result with rule_id and URL
"""

async def _create_data_protection_rule(request: CreateRuleRequest) -> CreateRuleResponse:
    """Handle create data protection rule requests from JSON string."""
    
    if not request.rule_json:
        return CreateRuleResponse(
            success=False,
            message="Rule json string is required",
            error="Rule json string is required"
        )
    
    LOGGER.info(f"Create Data Protection Rule from text, input: {request.rule_json}, preview_only: {request.preview_only}")
    
    try:
        common_message = WRONG_RULE_FORMAT_MESSAGE_TEMPLATE.format(user_input=request.rule_json)
        
        # Extract structured parameters from natural language
        structured_params = await get_json_to_data_protect_rule(request.rule_json)
        
        if not structured_params.get("rule_json"):
            return CreateRuleResponse(
                success=False,
                message=common_message,
                error="Failed to parse rule description"
            )
        
        # Check for validation failures
        status = structured_params.get("status", "")
        if "failed" in status:
            LOGGER.warning(f"Validation failed for DPS rule create: {structured_params.get('message')}")
            message = REFER_OBJECT_MESSAGE_TEMPLATE.format(error_message=structured_params.get('message'))
            return CreateRuleResponse(
                success=False,
                message=message,
                error=structured_params.get('message')
            )
        
        if "error" in status:
            LOGGER.warning(f"Error in DPS rule create: {structured_params.get('message')}")
            return CreateRuleResponse(
                success=False,
                message=structured_params.get('message', 'Unknown error occurred'),
                error=structured_params.get('message')
            )
        
        # Create summary for preview
        rule_json = structured_params['rule_json']
        summary = (
            f"**Name**: {rule_json.get('name', 'N/A')}. \n"
            f"**Description**: {rule_json.get('description', 'N/A')}. \n"
            f"**Action**: {rule_json.get('action', 'N/A')}. \n"
            f"**Trigger**: {rule_json.get('trigger', 'N/A')}"
        )
        
        # Get the payload for rule creation
        payload = structured_params.get('rule_map_json', {})
        
        # PREVIEW MODE - Show preview and ask for confirmation
        if request.preview_only:
            preview_msg = f"""**RULE PREVIEW**

                            Ready to create data protection rule:
                            {summary}
                            
                            Do you want to proceed? Reply **yes** to confirm or **no** to cancel.
                            """
            return CreateRuleResponse(
                success=True,
                message=preview_msg,
                preview_json=payload
            )
        
        # CREATE MODE - Actually create the rule
        result = await create_rule_from_payload(payload)
        
        # Build URL based on environment
        if settings.di_env_mode.upper() == ENV_MODE_SAAS:
            url_prefix = str(tool_helper_service.ui_base_url) + "/governance/rules/dataProtection/view/"
        else:
            url_prefix = str(tool_helper_service.ui_base_url) + "/gov/rules/dataProtection/view/"
        
        # Handle successful creation
        if result["success"] and result["guid"]:
            rule_id = result["guid"]
            rule_url = url_prefix + rule_id
            success_message = f"\n✅ **Rule created successfully!**\n\n**Name**: {result['name']}. \n**View the rule**: {rule_url}"
            return CreateRuleResponse(
                success=True,
                message=success_message,
                rule_id=rule_id,
                url=rule_url
            )
        else:
            error_message = f"Data protection rule API returned success but missing expected metadata, response: {result['response']}"
            return CreateRuleResponse(
                success=False,
                message=error_message,
                error=error_message
            )
    
    except ExternalAPIError as e:
        error_msg = f"Failed to create rule due to external API error: {str(e)}"
        LOGGER.error(error_msg)
        return CreateRuleResponse(
            success=False,
            message=error_msg,
            error=str(e)
        )
    except Exception as e:
        error_msg = f"Failed in rule creation: {type(e).__name__}: {str(e)}"
        LOGGER.error(error_msg)
        return CreateRuleResponse(
            success=False,
            message=error_msg,
            error=f"{type(e).__name__}: {str(e)}"
        )

@service_registry.tool(
    name="create_data_protection_rule",
    description=RULE_CREATION_DESCRIPTION,
    tags={"create", "data_protection_rules", "json", "llm_integration"},
    meta={"version": "2.0", "service": "data_protection_rules"},
    annotations={
        "title": "Creates a data protection rule from a JSON string",
        "destructiveHint": True
    }
)
@auto_context
async def create_data_protection_rule(
    rule_json: str,
    preview_only: bool = True
) -> CreateRuleResponse:
    """
    Wrapper version for rule creation.

    This function expands CreateRuleRequest object into individual parameters.
    For direct API usage with request objects, use create_data_protection_rule instead.
    """
    
    request = CreateRuleRequest(
        rule_json=rule_json,
        preview_only=preview_only
    )
    
    # Call the natural language create function
    return await _create_data_protection_rule(request)
