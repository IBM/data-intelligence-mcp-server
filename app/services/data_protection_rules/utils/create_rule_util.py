# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
# This file has been modified with the assistance of IBM Bob AI tool

from typing import Dict, Any, Optional, Tuple, List
from app.core.auth import get_access_token
from app.services.data_protection_rules.models.create_rule import Rule, CreateRuleResponse, TriggerCondition, RuleAction
from app.shared.utils.http_client import get_http_client
from app.services.constants import JSON_CONTENT_TYPE, DP_TRANSFORM
from app.core.settings import settings
from app.services.constants import DPR_RULES
from app.shared.logging import LOGGER
from app.shared.exceptions.base import ExternalAPIError, ServiceError

# Constants
ASSET_INFERRED_CLASSIFICATION = "Asset.InferredClassification"
ASSET_TAGS = "Asset.Tags"
ASSET_NAME = "Asset.Name"
ASSET_OWNER = "Asset.Owner"

async def get_text_to_data_protect_rule(input_text: str) -> Dict[str, Any]:
    """
    Call dp-transform service to get data protect rule json from text (SaaS only).

    Args:
        input_text (string): a natural language string for data protect rule create

    Returns:
       dict: include rule json in the dict
    """
    token = await get_access_token()
    headers = {
        "Content-Type": JSON_CONTENT_TYPE,
        "Authorization": token,
    }
    client = get_http_client()

    payload = {"input": input_text}

    try:
        response = await client.post(
            url=f"{settings.di_service_url}{DP_TRANSFORM}/text_to_rule",
            headers=headers,
            data=payload,
        )

        return {
            "rule_json": response.get("rule_json", {}),
            "status": response.get("status", {}),
            "rule_map_json": response.get("rule_map_json", {}),
            "message": response.get("message", {})
        }
    except ExternalAPIError as e:
        LOGGER.error(f"Failed to call dp-transform service: {str(e)}")
        raise ExternalAPIError(f"Failed to convert text to data protection rule: {str(e)}")
    except Exception as e:
        LOGGER.error(f"Unexpected error calling dp-transform service: {str(e)}")
        raise ServiceError(f"Failed to convert text to data protection rule: {str(e)}")


async def create_rule_util(rule: Rule) -> str:
    """Create a data protection rule in the system."""
    auth = await get_access_token()
    headers = {
        "Content-Type": JSON_CONTENT_TYPE,
        "Authorization": auth
    }
    client = get_http_client()


    response = await client.post(
        f"{settings.di_service_url}{DPR_RULES}",
        headers=headers,
        data=rule.model_dump(),
    )

    rule_id = response.get("metadata", {}).get("guid", "")
    return  rule_id


async def create_rule_from_payload(payload: Dict) -> Dict:
    """Create the actual rule via API.
    
    Returns:
        Dict with keys: success (bool), guid (str), name (str), response (dict)
    """
    token = await get_access_token()
    headers = {
        "Content-Type": JSON_CONTENT_TYPE,
        "Authorization": token,
    }
    client = get_http_client()

    response = await client.post(
        url=f"{settings.di_service_url}/v3/enforcement/rules",
        headers=headers,
        data=payload,
    )

    # For successful creation (201)
    if response.get("metadata", {}).get("guid"):
        guid = response["metadata"]["guid"]
        return {
            "success": True,
            "guid": guid,
            "name": payload.get('name', 'N/A'),
            "response": response
        }
    else:
        return {
            "success": False,
            "guid": None,
            "name": payload.get('name', 'N/A'),
            "response": response
        }


# ============================================================================
# Helper Functions for create_rule Refactoring
# ============================================================================

async def validate_operator_compatibility(conditions: List[TriggerCondition]) -> Optional[CreateRuleResponse]:
    """
    Validate that operators are compatible with field types.
    
    Returns:
        CreateRuleResponse with error if validation fails, None if valid
    """
    for idx, cond in enumerate(conditions):
        # Data classes and tags MUST use CONTAINS operator
        if cond.field in [ASSET_INFERRED_CLASSIFICATION, ASSET_TAGS]:
            if cond.operator != "CONTAINS":
                field_name = "Data class" if cond.field == ASSET_INFERRED_CLASSIFICATION else "Tags"
                return CreateRuleResponse(
                    success=False,
                    message=f"❌ Error in condition #{idx + 1}: {field_name} must use 'CONTAINS' operator.\n\nYou used: '{cond.operator}'\nRequired: 'CONTAINS'\n\nPlease retry with operator='CONTAINS'",
                    error=f"Invalid operator for {cond.field}: {cond.operator}. Must use CONTAINS.",
                )
    return None


async def validate_and_resolve_data_classes(
    conditions: List[TriggerCondition],
    metadata: Any
) -> Tuple[Optional[CreateRuleResponse], List[Dict]]:
    """
    Validate data class conditions and resolve ambiguous references.
    
    Returns:
        Tuple of (error_response, ambiguous_conditions)
        - error_response: CreateRuleResponse if validation fails, None if valid
        - ambiguous_conditions: List of ambiguous condition info
    """
    from app.services.data_protection_rules.utils.search_rhs_terms import search_rhs_terms
    
    ambiguous_conditions = []

    for idx, cond in enumerate(conditions):
        if cond.field != ASSET_INFERRED_CLASSIFICATION:
            continue
            
        error_response = await _process_data_class_condition(
            cond, idx, metadata, ambiguous_conditions
        )
        if error_response:
            return error_response, []

    return None, ambiguous_conditions


async def _process_data_class_condition(
    cond: TriggerCondition,
    idx: int,
    metadata: Any,
    ambiguous_conditions: List[Dict]
) -> Optional[CreateRuleResponse]:
    """Process a single data class condition."""
    from app.services.data_protection_rules.utils.search_rhs_terms import search_rhs_terms
    
    value = cond.value
    
    # If value looks like a globalid, skip validation
    if value.startswith("$") and len(value) >= 20:
        return None
    
    try:
        search_result = await search_rhs_terms(value.lstrip("$"), "data_class")
        
        if search_result.total_count == 0:
            return CreateRuleResponse(
                success=False,
                message=f"No data class found matching '{value}' in condition #{idx + 1}. Please use search_terms to find valid data classes.",
                error="Data class not found",
            )
        
        if search_result.total_count > 1:
            ambiguous_conditions.append({
                "index": idx + 1,
                "value": value,
                "matches": search_result.entities,
            })
        elif search_result.total_count == 1:
            # Auto-fix with the correct globalid
            matched_entity = search_result.entities[0]
            cond.value = matched_entity.global_id
            metadata.data_class_names[matched_entity.global_id] = matched_entity.name
    
    except Exception:
        # If validation fails, continue (maybe it's already a valid globalid)
        pass
    
    return None


def format_ambiguous_conditions_error(ambiguous_conditions: List[Dict]) -> CreateRuleResponse:
    """Format error message for ambiguous data class conditions."""
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
        message=f"""Ambiguous data class reference(s) found:

{all_ambiguous}

Please specify which data class to use for each condition.

Example: "For condition 1 use SSN-US, for condition 2 use Email Address"
""",
        error="Ambiguous data class references - multiple matches found",
    )


def build_trigger_array(conditions: List[TriggerCondition], combine_with: str) -> List:
    """Build the trigger array from conditions."""
    trigger = []
    for i, cond in enumerate(conditions):
        part = _build_condition_part(cond)
        trigger.append(part)
        
        # Add combine operator between conditions
        if i < len(conditions) - 1:
            trigger.append(combine_with)
    
    return trigger


def _build_condition_part(cond: TriggerCondition) -> List:
    """Build a single condition part for the trigger array."""
    lhs = f"${cond.field}"
    rhs = _format_rhs_value(cond)
    
    # CONTAINS operator needs array format
    if cond.operator == "CONTAINS":
        rhs = [rhs]
    
    part = [lhs, cond.operator, rhs]
    
    if cond.negate:
        part = ["NOT", part]
    
    return part


def _format_rhs_value(cond: TriggerCondition) -> str:
    """Format the right-hand side value based on field type."""
    rhs = cond.value
    
    # Add prefixes based on field type
    if cond.field in [ASSET_NAME, ASSET_OWNER, ASSET_TAGS]:
        if not rhs.startswith("#"):
            rhs = f"#{rhs}"
    elif cond.field == ASSET_INFERRED_CLASSIFICATION and not rhs.startswith("$"):
        rhs = f"${rhs}"
    
    return rhs


async def get_display_value_for_condition(cond: TriggerCondition, metadata: Any) -> str:
    """Get display-friendly value for a condition."""
    from app.services.data_protection_rules.utils.search_rhs_terms import search_rhs_terms
    
    if cond.field == ASSET_INFERRED_CLASSIFICATION:
        clean_value = cond.value.lstrip("$")
        # If not in metadata, try to look it up for display
        if clean_value not in metadata.data_class_names:
            try:
                # Try searching by global_id directly
                search_result = await search_rhs_terms(clean_value, "data_class")
                if search_result.total_count >= 1:
                    # Use the first match's name
                    return search_result.entities[0].name
                else:
                    # If no results, just show the clean value without $
                    return clean_value
            except Exception:
                # If lookup fails, show the clean value without $
                return clean_value
        else:
            return metadata.get_value_display(cond.field, cond.value)
    else:
        return metadata.get_value_display(cond.field, cond.value)


async def generate_preview_message(
    input_data: Any,
    conditions: List[TriggerCondition],
    metadata: Any
) -> str:
    """Generate preview message for rule creation."""
    conditions_text = []
    for c in conditions:
        # Get display-friendly field name
        field_display = metadata.get_field_display_name(c.field)

        # Get display-friendly value
        value_display = await get_display_value_for_condition(c, metadata)

        # Build the condition string
        negate_prefix = "NOT " if c.negate else ""
        condition_str = f"{negate_prefix}{field_display} {c.operator} '{value_display}'"
        conditions_text.append(condition_str)

    # Show how conditions are combined
    combine_text = f" {input_data.combine_with} ".join(conditions_text)

    preview_msg = f"""**RULE PREVIEW**

**Name:** {input_data.name}
**Action:** {input_data.action}
**State:** {input_data.state}
**Description:** {input_data.description}

**Conditions (combined with {input_data.combine_with}):**
{chr(10).join(f"- {c}" for c in conditions_text)}

**Logic:** {combine_text}

---

Ready to create this rule? Reply **yes** to confirm or **no** to cancel.
"""
    return preview_msg


async def execute_rule_creation(
    input_data: Any,
    trigger: List,
    url_prefix: str
) -> CreateRuleResponse:
    """Execute the actual rule creation."""
    try:
        rule = Rule(
            name=input_data.name,
            description=input_data.description,
            trigger=trigger,
            action=RuleAction(name=input_data.action),
            state=input_data.state,
            governance_type_id="Access",
        )

        rule_id = await create_rule_util(rule)

        url = url_prefix + rule_id
        success_msg = f"""✅ **Rule created successfully!**

**Name:** {input_data.name}
**Rule ID:** {rule_id}
**Status:** {input_data.state}
**URL:** {url}

The rule is now active in your governance system.
"""

        return CreateRuleResponse(
            success=True, message=success_msg, rule_id=rule_id, url=url
        )

    except Exception as e:
        return CreateRuleResponse(
            success=False,
            message=f"Failed to create rule: {str(e)}",
            error=str(e),
        )
