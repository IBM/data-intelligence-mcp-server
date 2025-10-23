# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from typing import Literal
from app.core.registry import service_registry
from app.services.data_protection_rules.models.create_rule import (
    CreateRuleRequest,
    CreateRuleResponse,
    Rule,
    RuleAction,
    TriggerCondition,
)
from app.core.settings import settings, ENV_MODE_SAAS
from app.services.data_protection_rules.utils.check_rule_exists import check_rule_exists
from app.services.data_protection_rules.utils.create_rule_util import create_rule_util
from app.services.data_protection_rules.utils.search_rhs_terms import search_rhs_terms
from app.shared.logging.generate_context import auto_context


@service_registry.tool(
    name="data_protection_rule_create",
    description="""
Create a data protection rule with automatic preview.

CRITICAL FOR AGENTS: This tool returns a 'display_to_user' field that MUST be shown
to the user exactly as returned. DO NOT summarize, paraphrase, or rewrite it.
Show the full text to the user so they can see the complete preview.

IMPORTANT LIMITATIONS:
- All conditions are combined with a SINGLE operator (either AND or OR via combine_with parameter)
- Complex nested logic like "(A AND B) OR C" is NOT supported
- If you need multiple conditions, use combine_with="AND" or combine_with="OR"


WORKFLOW (call this tool twice):

1. FIRST CALL - Preview Mode:
   - Call with preview_only=true (this is the default)
   - Tool returns formatted preview in 'display_to_user' field
   - SHOW THE ENTIRE 'display_to_user' TEXT TO THE USER
   - Then ask: "Would you like to create this rule? (yes/no)"

2. SECOND CALL - Create Mode:
   - After user confirms with "yes"
   - Call again with preview_only=false and the EXACT SAME parameters
   - Tool creates the rule and returns rule_id and url

DO NOT set preview_only=false without showing the preview and getting user confirmation.
""",
)
@auto_context
async def create_rule(input: CreateRuleRequest) -> CreateRuleResponse:
    # Validate rule name doesn't exist
    if await check_rule_exists(input.name):
        return CreateRuleResponse(
            success=False,
            display_to_user=f"Error: A rule named '{input.name}' already exists. Please choose a different name.",
            error="Rule name already exists",
        )

    # VALIDATION: Check operator compatibility with field types
    for idx, cond in enumerate(input.conditions):
        # Data classes and tags MUST use CONTAINS operator
        if cond.field in ["Asset.InferredClassification", "Asset.Tags"]:
            if cond.operator != "CONTAINS":
                field_name = "Data class" if cond.field == "Asset.InferredClassification" else "Tags"
                return CreateRuleResponse(
                    success=False,
                    display_to_user=f"❌ Error in condition #{idx + 1}: {field_name} must use 'CONTAINS' operator.\n\nYou used: '{cond.operator}'\nRequired: 'CONTAINS'\n\nPlease retry with operator='CONTAINS'",
                    error=f"Invalid operator for {cond.field}: {cond.operator}. Must use CONTAINS.",
                )

    # VALIDATION: Check ALL data class conditions for ambiguity
    ambiguous_conditions = []

    for idx, cond in enumerate(input.conditions):
        if cond.field == "Asset.InferredClassification":
            value = cond.value

            # If value doesn't look like a globalid (should be long UUID-like string)
            if not value.startswith("$") or len(value) < 20:
                # Search to see if this matches multiple data classes
                try:
                    search_result = await search_rhs_terms(
                        value.lstrip("$"), "data_class"
                    )

                    if search_result.total_count == 0:
                        return CreateRuleResponse(
                            success=False,
                            display_to_user=f"No data class found matching '{value}' in condition #{idx + 1}. Please use search_terms to find valid data classes.",
                            error="Data class not found",
                        )

                    if search_result.total_count > 1:
                        # Track this ambiguous condition
                        ambiguous_conditions.append(
                            {
                                "index": idx + 1,
                                "value": value,
                                "matches": search_result.entities,
                            }
                        )

                    # If exactly 1 match, auto-fix it with the correct globalid
                    if search_result.total_count == 1:
                        matched_entity = search_result.entities[0]
                        cond.value = matched_entity.global_id
                        # Store the display name in metadata for preview
                        input.metadata.data_class_names[matched_entity.global_id] = matched_entity.name

                except Exception:
                    # If validation fails, continue (maybe it's already a valid globalid)
                    pass

    # If we found ANY ambiguous conditions, reject and ask for ALL of them
    if ambiguous_conditions:
        ambiguous_text = []
        for amb in ambiguous_conditions:
            matches_text = "\n".join(
                [
                    f"   {i + 1}. **{e.name}** (globalid: `{e.global_id}`)"
                    for i, e in enumerate(amb["matches"])
                ]
            )
            ambiguous_text.append(f"""**Condition #{amb["index"]}:** '{amb["value"]}'
Found {len(amb["matches"])} matches:
{matches_text}
""")

        all_ambiguous = "\n\n".join(ambiguous_text)

        return CreateRuleResponse(
            success=False,
            display_to_user=f"""Ambiguous data class reference(s) found:

{all_ambiguous}

Please specify which data class to use for each condition.

Example: "For condition 1 use SSN-US, for condition 2 use Email Address"
""",
            error="Ambiguous data class references - multiple matches found",
        )

    # Build trigger array
    trigger = []
    for i, cond in enumerate(input.conditions):
        lhs = f"${cond.field}"
        rhs = cond.value

        # Add prefixes based on field type
        if cond.field in ["Asset.Name", "Asset.Owner", "Asset.Tags"]:
            if not rhs.startswith("#"):
                rhs = f"#{rhs}"
        elif cond.field == "Asset.InferredClassification":
            if not rhs.startswith("$"):
                rhs = f"${rhs}"

        # CONTAINS operator needs array format
        if cond.operator == "CONTAINS":
            rhs = [rhs]

        part = [lhs, cond.operator, rhs]

        if cond.negate:
            part = ["NOT", part]

        trigger.append(part)

        # Add combine operator between conditions (use combine_with from input)
        if i < len(input.conditions) - 1:
            trigger.append(input.combine_with)

    # Build rule structure
    rule_dict = {
        "name": input.name,
        "description": input.description,
        "trigger": trigger,
        "action": {"name": input.action},
        "state": input.state,
        "governance_type_id": "Access",
    }

    # PREVIEW MODE - Use metadata for human-readable display
    if input.preview_only:
        conditions_text = []
        for c in input.conditions:
            # Get display-friendly field name
            field_display = input.metadata.get_field_display_name(c.field)

            # Get display-friendly value
            # For data classes without metadata, try to fetch the name on-the-fly
            if c.field == "Asset.InferredClassification":
                clean_value = c.value.lstrip("$")
                # If not in metadata, try to look it up for display
                if clean_value not in input.metadata.data_class_names:
                    try:
                        # Try searching by global_id directly
                        search_result = await search_rhs_terms(clean_value, "data_class")
                        if search_result.total_count >= 1:
                            # Use the first match's name
                            value_display = search_result.entities[0].name
                        else:
                            # If no results, just show the clean value without $
                            value_display = clean_value
                    except Exception:
                        # If lookup fails, show the clean value without $
                        value_display = clean_value
                else:
                    value_display = input.metadata.get_value_display(c.field, c.value)
            else:
                value_display = input.metadata.get_value_display(c.field, c.value)

            # Build the condition string
            negate_prefix = "NOT " if c.negate else ""
            condition_str = f"{negate_prefix}{field_display} {c.operator} '{value_display}'"
            conditions_text.append(condition_str)

        # Show how conditions are combined
        combine_text = f" {input.combine_with} ".join(conditions_text)

        preview_msg = f"""**RULE PREVIEW**

**Name:** {input.name}
**Action:** {input.action}
**State:** {input.state}
**Description:** {input.description}

**Conditions (combined with {input.combine_with}):**
{chr(10).join(f"- {c}" for c in conditions_text)}

**Logic:** {combine_text}

---

Ready to create this rule? Reply **yes** to confirm or **no** to cancel.
"""
        return CreateRuleResponse(
            success=True, display_to_user=preview_msg, preview_json=rule_dict
        )

    # CREATE MODE - Actually create the rule
    try:
        rule = Rule(
            name=input.name,
            description=input.description,
            trigger=trigger,
            action=RuleAction(name=input.action),
            state=input.state,
            governance_type_id="Access",
        )

        rule_id = await create_rule_util(rule)

        if settings.di_env_mode.upper() == ENV_MODE_SAAS:
            url_prefix = settings.di_service_url.replace("https://api.", "https://") + "/governance/rules/dataProtection/view/"
        else:
            url_prefix = settings.di_service_url + "/gov/rules/dataProtection/view/"

        url = url_prefix + rule_id
        success_msg = f"""✅ **Rule created successfully!**

**Name:** {input.name}
**Rule ID:** {rule_id}
**Status:** {input.state}
**URL:** {url}

The rule is now active in your governance system.
"""

        return CreateRuleResponse(
            success=True, display_to_user=success_msg, rule_id=rule_id, url=url
        )

    except Exception as e:
        return CreateRuleResponse(
            success=False,
            display_to_user=f"Failed to create rule: {str(e)}",
            error=str(e),
        )


@service_registry.tool(
    name="data_protection_rule_create",
    description="""
Create a data protection rule with automatic preview (Watsonx Orchestrator compatible).

⚠️ CRITICAL FOR AGENTS: This tool returns a 'display_to_user' field that MUST be shown
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
   - Tool returns formatted preview in 'display_to_user' field
   - SHOW THE ENTIRE 'display_to_user' TEXT TO THE USER
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
    Watsonx Orchestrator compatible version that expands CreateRuleRequest object into individual parameters.

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
        CreateRuleResponse with success status and display_to_user message

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

    # Build the CreateRuleRequest object
    request = CreateRuleRequest(
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
