# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This file has been modified with the assistance of IBM Bob AI tool

from app.core.registry import prompt_registry


@prompt_registry.prompt(
    name="Data Protection Rule Creation Guide",
    description="Guide users through creating data protection rules to enforce data governance policies with configurable actions (deny/redact/filter row/anonymize/pseudonymize)"
)
def create_rule_guide_prompt(
    rule_description: str
) -> str:
    """
    Provides guidance on creating data protection rules to enforce data governance policies.
    
    This prompt helps users create rules based on trigger conditions including user groups,
    governance artifacts, data assets name or schema, and tags with configurable actions to control data access and usage.
    
    Args:
        rule_description: Natural language description of the rule including the action and trigger conditions
                         (e.g., "Redact SSN data class for external user group",
                          "Deny access to assets tagged as sensitive for contractor user group",
                          "Anonymize credit card data for all users except admin group")
        governance_artifacts: Optional governance artifacts to use in conditions (e.g., "data classes: SSN, Credit Card; classifications: PII; business terms: Customer Data")
    """
    prompt_content = f"""You are a data governance and protection assistant. I need help creating a data protection rule to enforce data governance policies.

**My Requirements:**
* Rule description (including action and trigger conditions): '{rule_description}'

**Please help me with the following steps:**

1. **Analyze the Rule Requirements:**
   - Parse the rule description to extract the action (Deny/Redact/Filter Row/Anonymize/Pseudonymize)
   - Identify the trigger conditions from the description (user groups, user names, governance artifacts, data assets name or schema, tags)
   - Understand what data needs to be protected
   - Identify any governance artifacts needed (data classes, classifications, business terms)

2. **Search for Required Governance Artifacts:**
   - If the rule references data classes, classifications, or business terms, use the search_governance_artifacts tool to verify they exist
   - Provide the correct names and IDs for any governance artifacts
   - If artifacts don't exist, suggest creating them first or using alternative artifacts

3. **Create the Rule with Preview:**
   - Use create_data_protection_rule_from_text with structured parameters
   - ALWAYS set preview_only=true on the first call to show the preview
   - Display the complete preview to me for review

4. **Confirm and Create:**
   - After I review the preview, ask if I want to proceed
   - If I confirm, call the same tool again with preview_only=false to create the rule
   - Provide the rule ID and URL for accessing the created rule

**Expected Output:**
* Analysis of the rule requirements and trigger conditions
* List of governance artifacts needed (with verification status)
* Preview of the rule before creation
* Confirmation prompt before actual creation
* Final rule details with ID and access URL

**Important Notes:**
- Trigger conditions can include: user groups, user names, governance artifacts (data classes, classifications, business terms), data assets name or schema, and tags
- All conditions in a rule are combined with a single operator (AND or OR)
- Complex nested logic like "(A AND B) OR C" is not supported
- For data classes and tags, always use the CONTAINS operator
- Available actions: Deny (block access), Redact (mask data), Filter Row (remove rows), Anonymize (remove identifiers), Pseudonymize (replace with pseudonyms)
- Rules can be created in draft or active state
- Preview the rule before creation to ensure it matches requirements

Please guide me through creating this data protection rule step by step."""

    return prompt_content
