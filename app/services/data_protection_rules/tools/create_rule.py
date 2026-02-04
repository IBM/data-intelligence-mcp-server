# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
# This file has been modified with the assistance of IBM Bob AI tool

from typing import Literal
from app.core.registry import service_registry
from app.services.data_protection_rules.models.create_rule import (
    NaturalLanguageCreateRuleRequest,
    StructuredCreateRuleRequest,
    CreateRuleResponse,
    TriggerCondition,
)
from app.core.settings import settings, ENV_MODE_SAAS
from app.services.data_protection_rules.utils.check_rule_exists import check_rule_exists
from app.services.data_protection_rules.utils.create_rule_util import (
    create_rule_from_payload,
    get_text_to_data_protect_rule,
    validate_operator_compatibility,
    validate_and_resolve_data_classes,
    format_ambiguous_conditions_error,
    build_trigger_array,
    generate_preview_message,
    execute_rule_creation,
)
from app.shared.logging.generate_context import auto_context
from app.shared.logging import LOGGER
from app.shared.exceptions.base import ExternalAPIError


# ============================================================================
# Natural Language Rule Creation (SaaS only)
# ============================================================================

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


@service_registry.tool(
    name="create_data_protection_rule_from_text",
    description="""Create a data protection rule using natural language description (SaaS only).

USE THIS TOOL when user wants to create a new rule using natural language in SaaS environment.
The system will automatically validate any referenced objects (classifications,
user groups, etc.) and provide helpful error messages if they don't exist.

DO NOT query for artifacts first - this tool handles validation automatically.
DO NOT truncate user input, please use full user input as rule_description.

WORKFLOW (call this tool twice):

1. FIRST CALL - Preview Mode:
   - Call with preview_only=true (this is the default)
   - Tool returns formatted preview
   - SHOW THE PREVIEW TO THE USER
   - Then ask: "Would you like to create this rule? (yes/no)"

2. SECOND CALL - Create Mode:
   - After user confirms with "yes"
   - Call again with preview_only=false and the EXACT SAME rule_description
   - Tool creates the rule and returns rule_id and url

DO NOT set preview_only=false without showing the preview and getting user confirmation.

Args:
    request: NaturalLanguageCreateRuleRequest with rule_description and preview_only flag

Returns:
    CreateRuleResponse with success status and message
""",
    tags={"create", "data_protection_rules", "natural_language", "saas"},
    meta={"version": "1.0", "service": "data_protection_rules"},
)
@auto_context
async def create_data_protection_rule_from_text(request: NaturalLanguageCreateRuleRequest) -> CreateRuleResponse:
    """Handle create data protection rule requests from natural language (SaaS only)."""
    
    # Check if SaaS mode
    if settings.di_env_mode.upper() != ENV_MODE_SAAS:
        return CreateRuleResponse(
            success=False,
            message="Natural language rule creation is only supported in SaaS mode. Please use the structured rule creation tool for CP4D.",
            error="Not supported in CP4D"
        )
    
    if not request.rule_description:
        return CreateRuleResponse(
            success=False,
            message="Rule description is required",
            error="Rule description is required"
        )
    
    LOGGER.info(f"Create Data Protection Rule from text, input: {request.rule_description}, preview_only: {request.preview_only}")
    
    try:
        common_message = WRONG_RULE_FORMAT_MESSAGE_TEMPLATE.format(user_input=request.rule_description)
        
        # Extract structured parameters from natural language
        structured_params = await get_text_to_data_protect_rule(request.rule_description)
        
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
            url_prefix = str(settings.di_service_url).replace("https://api.",
                                                              "https://") + "/governance/rules/dataProtection/view/"
        else:
            url_prefix = str(settings.di_service_url) + "/gov/rules/dataProtection/view/"
        
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
        error_msg = f"Failed in rule creation: {str(e)}"
        LOGGER.error(error_msg)
        return CreateRuleResponse(
            success=False,
            message=error_msg,
            error=str(e)
        )


# ============================================================================
# Structured Rule Creation (CP4D)
# ============================================================================

@service_registry.tool(
    name="create_data_protection_rule",
    description="""
Create a data protection rule with automatic preview (works in CP4D).

CRITICAL FOR AGENTS: This tool returns a 'message' field that MUST be shown
to the user exactly as returned. DO NOT summarize, paraphrase, or rewrite it.
Show the full text to the user so they can see the complete preview.

IMPORTANT LIMITATIONS:
- All conditions are combined with a SINGLE operator (either AND or OR via combine_with parameter)
- Complex nested logic like "(A AND B) OR C" is NOT supported
- If you need multiple conditions, use combine_with="AND" or combine_with="OR"


WORKFLOW (call this tool twice):

1. FIRST CALL - Preview Mode:
   - Call with preview_only=true (this is the default)
   - Tool returns formatted preview in 'message' field
   - SHOW THE ENTIRE 'message' TEXT TO THE USER
   - Then ask: "Would you like to create this rule? (yes/no)"

2. SECOND CALL - Create Mode:
   - After user confirms with "yes"
   - Call again with preview_only=false and the EXACT SAME parameters
   - Tool creates the rule and returns rule_id and url

DO NOT set preview_only=false without showing the preview and getting user confirmation.
""",
)
@auto_context
async def create_rule(input: StructuredCreateRuleRequest) -> CreateRuleResponse:
    """Create a data protection rule with structured parameters (works in CP4D)."""
    
    # Check if CP4D mode - structured creation only supported in CP4D
    if settings.di_env_mode.upper() == ENV_MODE_SAAS:
        return CreateRuleResponse(
            success=False,
            message="Structured rule creation is only supported in CP4D mode. Please use the natural language rule creation tool for SaaS.",
            error="Not supported in SaaS"
        )
    
    # Validate rule name doesn't exist
    if await check_rule_exists(input.name):
        return CreateRuleResponse(
            success=False,
            message=f"Error: A rule named '{input.name}' already exists. Please choose a different name.",
            error="Rule name already exists",
        )

    # Validate operator compatibility
    error_response = await validate_operator_compatibility(input.conditions)
    if error_response:
        return error_response

    # Validate and resolve data class references
    error_response, ambiguous_conditions = await validate_and_resolve_data_classes(
        input.conditions, input.metadata
    )
    if error_response:
        return error_response
    
    # Handle ambiguous conditions
    if ambiguous_conditions:
        return format_ambiguous_conditions_error(ambiguous_conditions)

    # Build trigger array
    trigger = build_trigger_array(input.conditions, input.combine_with)

    # Build rule structure
    rule_dict = {
        "name": input.name,
        "description": input.description,
        "trigger": trigger,
        "action": {"name": input.action},
        "state": input.state,
        "governance_type_id": "Access",
    }

    # PREVIEW MODE
    if input.preview_only:
        preview_msg = await generate_preview_message(input, input.conditions, input.metadata)
        return CreateRuleResponse(
            success=True, message=preview_msg, preview_json=rule_dict
        )

    # CREATE MODE
    url_prefix = (
        str(settings.di_service_url).replace("https://api.", "https://") + "/governance/rules/dataProtection/view/"
        if settings.di_env_mode.upper() == ENV_MODE_SAAS
        else str(settings.di_service_url) + "/gov/rules/dataProtection/view/"
    )
    
    return await execute_rule_creation(input, trigger, url_prefix)


@service_registry.tool(
    name="create_data_protection_rule",
    description="""
Create a data protection rule with automatic preview (Watsonx Orchestrator compatible).

⚠️ CRITICAL FOR AGENTS: This tool returns a 'message' field that MUST be shown
to the user exactly as returned. DO NOT summarize, paraphrase, or rewrite it.
Show the full text to the user so they can see the complete preview.

═══════════════════════════════════════════════════════════════════════════════
CONDITION STRUCTURE - MUST USE EXACTLY THESE FIELDS
═══════════════════════════════════════════════════════════════════════════════
Each condition dictionary MUST have these fields:
{
  "field": "Asset.InferredClassification",  // Required - see mapping below
  "operator": "CONTAINS",                    // Required - see options below
  "value": "ssn",                           // Required - the value to match
  "negate": false                           // Optional - defaults to false
}

⚠️ CRITICAL: Do NOT use "type" - use "field" instead!
⚠️ CRITICAL: Always include "operator" - it is required!

═══════════════════════════════════════════════════════════════════════════════
FIELD MAPPING - Natural Language → Technical Field Name
═══════════════════════════════════════════════════════════════════════════════
When user says:              Use this field value:
- "dataclass" / "data class" → "Asset.InferredClassification"
- "tag" / "tags"            → "Asset.Tags"
- "asset name" / "table"    → "Asset.Name"
- "owner"                   → "Asset.Owner"
- "business term"           → "Business.Term"

═══════════════════════════════════════════════════════════════════════════════
OPERATOR OPTIONS
═══════════════════════════════════════════════════════════════════════════════
⚠️ CRITICAL OPERATOR RULES:
- For "Asset.Name" → use "CONTAINS", "LIKE"
- For "Asset.Owner" → ONLY use "CONTAINS"
- For "Asset.Schema" → ONLY use "CONTAINS"
- For "Business.Term" → ONLY use "CONTAINS"
- For "Asset.InferredClassification" (data classes) → ALWAYS use "CONTAINS"
- For "Asset.ColumnName" → use "CONTAINS", "LIKE"
- For "Asset.UserClassification" → ALWAYS use "CONTAINS"
- For "Asset.Tags" → ALWAYS use "CONTAINS"
- For "User.Group" → ALWAYS use "CONTAINS"
- For "User.Name" → ALWAYS use "CONTAINS"

DO NOT use EQUALS for data classes or tags - it will not work!

Operator meanings:
- "CONTAINS" - Check if value exists in the asset (required for data classes and tags)
- "LIKE"     - Pattern matching with wildcards (e.g., "customer%")


When user says "contains" or doesn't specify → use "CONTAINS"

═══════════════════════════════════════════════════════════════════════════════
COMPLETE EXAMPLE
═══════════════════════════════════════════════════════════════════════════════
User request: "create deny rule when asset contains dataclass ssn and tag test"

Correct JSON to send:
{
  "name": "sample",
  "description": "Deny rule for assets with SSN data class and test tag",
  "action": "Deny",
  "conditions": [
    {
      "field": "Asset.InferredClassification",
      "operator": "CONTAINS",  ← MUST be CONTAINS for data classes!
      "value": "ssn",
      "negate": false
    },
    {
      "field": "Asset.Tags",
      "operator": "CONTAINS",  ← MUST be CONTAINS for tags!
      "value": "test",
      "negate": false
    }
  ],
  "combine_with": "AND",
  "state": "active",
  "preview_only": true
}

═══════════════════════════════════════════════════════════════════════════════
WORKFLOW - TWO STEP PROCESS (MANDATORY!)
═══════════════════════════════════════════════════════════════════════════════
⚠️⚠️⚠️ CRITICAL: You MUST call this tool TWICE - preview first, then create! ⚠️⚠️⚠️

STEP 1 - PREVIEW MODE (ALWAYS DO THIS FIRST):
   - ALWAYS set preview_only=true on your FIRST call
   - Tool returns formatted preview in 'message' field
   - SHOW THE ENTIRE 'message' TEXT TO THE USER
   - Ask user: "Would you like to create this rule? (yes/no)"
   - WAIT for user confirmation

STEP 2 - CREATE MODE (ONLY after user says "yes"):
   - Set preview_only=false
   - Use the EXACT SAME parameters from step 1
   - Tool creates the rule and returns rule_id and url

⚠️ NEVER set preview_only=false on your first call!
⚠️ NEVER skip showing the preview to the user!
⚠️ NEVER create the rule without user confirmation!

If you skip the preview, the user will not have a chance to review and confirm the rule.

═══════════════════════════════════════════════════════════════════════════════
IMPORTANT LIMITATIONS
═══════════════════════════════════════════════════════════════════════════════
- All conditions are combined with ONE operator (AND or OR via combine_with)
- Complex nested logic like "(A AND B) OR C" is NOT supported
- Use combine_with="AND" to require all conditions
- Use combine_with="OR" to require any condition
""",
)
@auto_context
async def wxo_create_rule(
    name: str,
    description: str,
    action: Literal["Allow", "Deny", "Transform"],
    conditions: list[dict],  # Each dict must have: field, operator, value, negate (optional)
    combine_with: Literal["AND", "OR"] = "AND",
    state: Literal["active", "draft"] = "active",
    preview_only: bool = True,
    ctx=None
) -> CreateRuleResponse:
    """
    Watsonx Orchestrator compatible version for STRUCTURED rule creation (works in CP4D).
    
    This function expands StructuredCreateRuleRequest object into individual parameters.
    For natural language rule creation, you can also use wxo_create_rule_from_text.

    Args:
        name: Rule name
        description: Rule description
        action: Action to take (Allow, Deny, Transform)
        conditions: List of condition dictionaries, each MUST have:
            - field: One of "Asset.Name", "Asset.InferredClassification", "Asset.Owner", "Business.Term", "Asset.Tags"
            - operator: One of "CONTAINS", "LIKE", "EQUALS", "IN"
            - value: The value to compare (str)
            - negate: Optional boolean, defaults to False
        combine_with: How to combine conditions (AND or OR)
        state: Rule state (active or draft)
        preview_only: If true, only show preview; if false, create the rule. DEFAULT IS TRUE - always preview first!

    Returns:
        CreateRuleResponse with success status and message

    Example for "deny when asset contains dataclass ssn and tag test":
        conditions = [
            {
                "field": "Asset.InferredClassification",
                "operator": "CONTAINS",
                "value": "ssn",
                "negate": False
            },
            {
                "field": "Asset.Tags",
                "operator": "CONTAINS",
                "value": "test",
                "negate": False
            }
        ]
    """
    
    # SAFETY CHECK: If preview_only is False but this looks like a first call, force preview
    # Check if context suggests this is an initial request (not a confirmation)
    if not preview_only and ctx:
        # Force preview mode on first call
        preview_only = True

    # Convert condition dictionaries to TriggerCondition objects
    trigger_conditions = [TriggerCondition(**cond) for cond in conditions]

    # Build the StructuredCreateRuleRequest object
    request = StructuredCreateRuleRequest(
        name=name,
        description=description,
        action=action,
        conditions=trigger_conditions,
        combine_with=combine_with,
        state=state,
        preview_only=preview_only
    )

    # Call the original create_rule function
    return await create_rule(request)


@service_registry.tool(
    name="create_data_protection_rule_from_text",
    description="""Create a data protection rule using natural language (Watsonx Orchestrator compatible, SaaS only).

USE THIS TOOL when user wants to create a rule using natural language in SaaS environment.
For CP4D or structured rule creation, use wxo_create_rule instead.

WORKFLOW (call this tool twice):

1. FIRST CALL - Preview Mode:
   - Call with preview_only=true (this is the default)
   - Tool returns formatted preview
   - SHOW THE PREVIEW TO THE USER
   - Then ask: "Would you like to create this rule? (yes/no)"

2. SECOND CALL - Create Mode:
   - After user confirms with "yes"
   - Call again with preview_only=false and the EXACT SAME rule_description
   - Tool creates the rule and returns rule_id and url

Args:
    rule_description: Natural language description of the rule
    preview_only: If true, only show preview; if false, create the rule. DEFAULT IS TRUE

Returns:
    CreateRuleResponse with success status and message
""",
    tags={"create", "data_protection_rules", "natural_language", "saas", "wxo"},
    meta={"version": "1.0", "service": "data_protection_rules"},
)
@auto_context
async def wxo_create_rule_from_text(
    rule_description: str,
    preview_only: bool = True
) -> CreateRuleResponse:
    """
    Watsonx Orchestrator compatible version for NATURAL LANGUAGE rule creation (SaaS only).
    
    This function expands NaturalLanguageCreateRuleRequest object into individual parameters.
    For structured rule creation or CP4D, use wxo_create_rule instead.
    """
    
    request = NaturalLanguageCreateRuleRequest(
        rule_description=rule_description,
        preview_only=preview_only
    )
    
    # Call the natural language create function
    return await create_data_protection_rule_from_text(request)
