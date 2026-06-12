# Copyright [2026] [IBM]
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

from app.core.registry import service_registry
from app.shared.logging.generate_context import auto_context
from app.shared.logging import LOGGER

# Full JSON schema and examples for data protection rules
FULL_RULE_SCHEMA_GUIDE = """
═══════════════════════════════════════════════════════════════════════════════
DATA PROTECTION RULE JSON SCHEMA AND EXAMPLES
═══════════════════════════════════════════════════════════════════════════════

This guide provides the complete JSON specification for creating data protection rules.

**STOP! READ THIS FIRST - ABSOLUTE PROHIBITIONS:**
These terms DO NOT EXIST and will cause IMMEDIATE FAILURE:
- $Column.Tag, $Column.Classification, $Asset.Classification, $govern.classification, $Data.Column

**CRITICAL CONSTRAINTS:**
1. Output ONLY valid JSON - no explanations, no markdown, no extra text
2. All terms MUST start with $ and be from VALID TERMS list
3. PREFIX RULES FOR VALUES:
   - $Asset.UserClassification, $Asset.InferredClassification, $Business.Term: values start with $ (e.g., ["$Personally Identifiable Information"])
   - $User.Name, $User.Role, $Asset.Owner: values start with # (e.g., ["#john.doe"])
   - $User.Group: values have NO prefix (e.g., ["HR_Managers"])
   - $Asset.Name, $Asset.Schema, $Asset.ColumnName, $Asset.Tags: values start with # (e.g., ["#customer_transactions"])

**AVAILABLE TERMS (ONLY THESE - NO OTHERS ALLOWED):**
⚠️ CRITICAL: You MUST use ONLY these exact terms. Any other term (like $Column.Tag, $Data.Column, etc.) is INVALID and will cause errors.

VALID TERMS:
- $Business.Term
- $Asset.UserClassification
- $Asset.InferredClassification
- $User.Name
- $User.Role
- $User.Group
- $Asset.Owner
- $Asset.Tags (plural - for tag-based conditions)
- $Asset.ColumnName (for column name matching)
- $Asset.Schema (for schema matching)
- $Asset.Name (for asset/table name matching)

INVALID TERMS (DO NOT USE - THESE WILL CAUSE ERRORS):
- $Column.Tag  DOES NOT EXIST
- $Column.Classification  DOES NOT EXIST
- $Asset.Classification  DOES NOT EXIST (use $Asset.UserClassification or $Asset.InferredClassification)
- $Data.Column  DOES NOT EXIST
- $Asset.Tag (singular)  DOES NOT EXIST (use $Asset.Tags plural)
- $govern.classification  DOES NOT EXIST
- Any term not in the VALID TERMS list above

IF YOU USE ANY INVALID TERM, THE RULE WILL FAIL!
THESE TERMS DO NOT EXIST IN THE API - DO NOT INVENT NEW TERMS!

**TRIGGER OPERATORS:**
- CONTAINS: ["$term", "CONTAINS", ["#value1", "#value2"]] or ["$term", "CONTAINS", ["$guid"]]
- LIKE: ["$term", "LIKE", "#abc"]

**TRIGGER LOGICAL OPERATORS:**
- AND: [condition1, "AND", condition2]
- OR: [condition1, "OR", condition2]
- NOT: ["NOT", condition]

**ALLOWED ACTIONS:**
- Transform (with subaction)
- Deny (simple)

**ALLOWED SUBACTIONS:**
redactColumns, redactDataClasses, redactTags, redactBusinessTerms, redactClassifications,
anonymizeColumns, anonymizeDataClasses, anonymizeTags, anonymizeBusinessTerms, anonymizeClassifications,
pseudonymizeColumns, pseudonymizeDataClasses, pseudonymizeTags, pseudonymizeBusinessTerms, pseudonymizeClassifications,
filter_include, filter_exclude, join_include, join_exclude

**TAG HANDLING RULES:**
CRITICAL: When user says "columns tagged X" or "anonymize columns tagged":
1. ✅ CORRECT subaction: "anonymizeTags" (NOT anonymizeColumns!)
2. ✅ CORRECT parameters: [{"name": "tag_names", "value": ["tag1", "tag2"]}]
3. ✅ CORRECT trigger for asset tags: "$Asset.Tags" with "CONTAINS" operator
4. ❌ NEVER use "anonymizeColumns" for tag-based rules
5. ❌ NEVER use "$Column.Tag" or "$govern.classification"
6. ❌ NEVER leave parameters empty []

🎯 EXACT PATTERN for "Anonymize columns tagged tag1 or tag2 in assets tagged tagasset":
{
  "action": {
    "name": "Transform",
    "subaction": {
      "name": "anonymizeTags",  ← NOT anonymizeColumns!
      "parameters": [{"name": "tag_names", "value": ["tag1", "tag2"]}]  ← NOT empty!
    }
  },
  "trigger": [["$Asset.Tags", "CONTAINS", ["#tagasset"]]]  ← Simple, not nested!
}

**ALLOWED PARAMETERS:**
column_names, dataclass_ids, tag_names, business_term_ids, classification_global_ids

**PARAMETER EXTRACTION RULES:**
- For column_names: Extract the actual column names mentioned in the user input (e.g., "salary", "CreditCardNumber")
- For table/asset names: Extract the actual table names mentioned (e.g., "customer_transactions", "employee_db")
- For group names: Extract the actual group names mentioned (e.g., "ExternalPartners", "HR_Managers")
- For schema names: Extract the actual schema names mentioned (e.g., "prod_finance", "employee_db")
- DO NOT use generic terms like $Data.Column in parameter values - always use the specific names from the input

**ALLOWED Predicate for filter_include and filter_exclude:**
- EQUALS
- LESS_THAN
- LESS_THAN_EQUALS
- GREATER_THAN
- GREATER_THAN_EQUALS

**EXAMPLES:**

Example #1 - TAG-BASED ANONYMIZATION:
Input: "Anonymize columns tagged tag1 or tag2 in assets tagged tagasset as draft"
Output:
{
  "action": {"name": "Transform", "subaction": {"name": "anonymizeTags", "parameters": [{"name": "tag_names", "value": ["tag1", "tag2"]}]}},
  "trigger": [["$Asset.Tags", "CONTAINS", ["#tagasset"]]],
  "name": "Anonymize columns tagged tag1 or tag2 in assets tagged tagasset",
  "description": "Anonymize columns tagged tag1 or tag2 in assets tagged tagasset",
  "governance_type_id": "Access",
  "state": "draft"
}

Example #2 - COLUMN MASKING:
Input: "Mask the CreditCardNumber column in the customer_transactions table for all users except those in the Fraud Analysts user group."
Output:
{
  "action": {"name": "Transform", "subaction": {"name": "redactColumns", "parameters": [{"name": "column_names", "value": ["CreditCardNumber"]}]}},
  "trigger": [["NOT", ["$User.Group", "CONTAINS", ["Fraud Analysts"]]], "AND", ["$Asset.Name", "CONTAINS", ["#customer_transactions"]]],
  "name": "Mask the CreditCardNumber column in the customer_transactions table",
  "description": "Mask the CreditCardNumber column in the customer_transactions table for all users except those in the Fraud Analysts user group.",
  "governance_type_id": "Access",
  "state": "active"
}

Example #3 - DENY WITH MULTIPLE CONDITIONS:
Input: "Deny access to any data assets classified as Personally Identifiable Information for business term contains address and data class is email and asset name like aaa"
Output:
{
  "action": {"name": "Deny"},
  "trigger": [["$Asset.UserClassification", "CONTAINS", ["$Personally Identifiable Information"]], "AND", ["$Business.Term", "CONTAINS", ["$address"]], "AND", ["$Asset.InferredClassification", "CONTAINS", ["$email"]], "AND", ["$Asset.Name", "LIKE", ["#aaa"]]],
  "name": "Deny access to any PII in catalog and asset combine rules",
  "description": "Deny access to any data assets classified as Personally Identifiable Information for catalog id is cc3333 and asset id is aa2222 and asset name like aaa.",
  "governance_type_id": "Access",
  "state": "active"
}

Example #4 - FILTER WITH PREDICATES:
Input: "Filter rows from the transactions table where transaction_amount > 10000 and region = 'APAC', but only for users in either the ExternalAuditors or ComplianceTeam groups and when the asset schema equals prod_finance."
Output:
{
  "action": {"name": "Transform", "subaction": {"name": "filter_include", "parameters": [{"name": "predicate", "value": [["$$transaction_amount", "GREATER_THAN", "#10000"], "AND", ["$$region", "EQUALS", "#'APAC'"]]}]}},
  "trigger": [["$Asset.Name", "CONTAINS", ["#transactions"]], "AND", ["$User.Group", "CONTAINS", ["ExternalAuditors", "ComplianceTeam"]], "AND", ["$Asset.Schema", "CONTAINS", ["#prod_finance"]]],
  "name": "Filter High-Value APAC Transactions for Auditors",
  "description": "Filter rows from the transactions table where transaction_amount > 10000 and region = 'APAC', but only for users in either the ExternalAuditors or ComplianceTeam groups and when the asset schema equals prod_finance.",
  "governance_type_id": "Access",
  "state": "active"
}

Example #5 - BUSINESS TERM ANONYMIZATION:
Input: "Substitute data for column with email business term when classification include any sensitive personal information or personally identification and column name like any aaa or bbb and asset name like ssn"
Output:
{
  "action": {"name": "Transform", "subaction": {"name": "anonymizeBusinessTerms", "parameters": [{"name": "business_term_ids", "value": ["email"]}]}},
  "trigger": [["$Asset.UserClassification", "CONTAINS", ["$sensitive personal information", "$personally identification"]], "AND", ["$Asset.ColumnName", "LIKE", ["#aaa", "#bbb"]], "AND", ["$Asset.Name", "LIKE", ["#ssn"]]],
  "name": "DSubstitute data for column with email business term when some rule match",
  "description": "Substitute data for column with email business term when classification include any sensitive personal information or personally identification and column name like any aaa or bbb and asset name like ssn",
  "governance_type_id": "Access",
  "state": "active"
}

Example #6 - DATA CLASS PSEUDONYMIZATION WITH OR/NOT:
Input: "Obfuscate all data class with Email and Account Number when asset owner is Yang or user name is Chen, or tag does not include tag1"
Output:
{
  "trigger": [["$Asset.Owner", "CONTAINS", ["#Yang"]], "OR", ["$User.Name", "CONTAINS", ["#Chen"]], "OR", ["NOT", ["$Asset.Tags", "CONTAINS", ["#tag1"]]]],
  "action": {"name": "Transform", "subaction": {"name": "pseudonymizeDataClasses", "parameters": [{"name": "dataclass_ids", "value": ["Email", "Account Number"]}]}},
  "name": "Obfuscate all data class with Email and Account Number when some rule match",
  "description": "Obfuscate all data class with Email and Account Number when asset owner is Yang or user name is Chen, or tag does not include tag1",
  "governance_type_id": "Access",
  "state": "active"
}

Example #7 - JOIN WITH REFERENCE ASSET:
Input: "Include rows from tables where the asset name contains 'COMMERCIAL_CLIENT', by joining with the COMMERCIAL_CLIENT reference asset from the AgentTest catalog. Only include rows where the source table's NAME column matches the reference table's EMAIL_ADDRESS column AND the reference table's COMMERCIAL_CLIENT column equals 'TRUE'"
Output:
{
  "trigger": ["$Asset.Name", "CONTAINS", ["#COMMERCIAL_CLIENT"]],
  "action": {"name": "Transform", "subaction": {"name": "join_include", "parameters": [{"name": "predicate", "value": [["$$source.NAME", "EQUALS", "$$references[0].EMAIL_ADDRESS"], "AND", ["$$references[0].COMMERCIAL_CLIENT", "EQUALS", "#'TRUE'"]]}, {"name": "references", "value": [{"catalog_id": "Default", "asset_id": "COMMERCIAL_CLIENT", "resource_key": "COMMERCIAL_CLIENT_resource_key"}]}]}},
  "name": "Include rows based on reference asset COMMERCIAL_CLIENT",
  "description": "Include rows from tables where the asset name contains 'COMMERCIAL_CLIENT', by joining with the COMMERCIAL_CLIENT reference asset from the AgentTest catalog. Only include rows where the source table's NAME column matches the reference table's EMAIL_ADDRESS column AND the reference table's COMMERCIAL_CLIENT column equals 'TRUE'",
  "governance_type_id": "Access",
  "state": "active"
}

**STEP-BY-STEP PARSING:**
1. Identify the ACTION: What should happen? (Transform/Deny/etc.)
2. Identify the SUBACTION: If Transform, what type? (anonymizeColumns, redactColumns, anonymizeTags, etc.)
   - If user says "columns tagged X" → use "anonymizeTags" with tag_names parameter
   - If user says "mask column Y" → use "redactColumns" with column_names parameter
3. Extract SPECIFIC VALUES: What column names, table names, group names, TAG NAMES are mentioned?
4. Build TRIGGER CONDITIONS: What conditions determine when this rule applies?
   - ONLY use terms from the VALID TERMS list above
   - For asset tag conditions: use "$Asset.Tags" (plural)
   - NEVER invent terms like "$Column.Tag"
5. Use EXACT VALUES in parameters, not generic terms
6. Use USER_INPUT and set in 'description' field
7. Generate a name from description and set in 'name' field
8. **VALIDATION CHECK**: Before outputting, verify ALL terms start with $ and are in the VALID TERMS list

═══════════════════════════════════════════════════════════════════════════════
END OF SCHEMA GUIDE
═══════════════════════════════════════════════════════════════════════════════
"""


@service_registry.tool(
    name="get_data_protection_rule_schema",
    annotations={
        "readOnlyHint": True,
        "title": "Get JSON Schema for Data Protection Rule Creation"
    },
    description="Returns the complete JSON schema, valid terms, examples, and formatting rules for creating data protection rules. Call this BEFORE creating a rule to understand the correct JSON format.",
    tags={"data_protection_rules", "schema", "reference"},
    meta={"version": "1.0", "service": "data_protection_rules"},
)
@auto_context
async def get_data_protection_rule_schema() -> str:
    """
    Returns the full JSON schema and examples for data protection rules.
    
    This tool provides:
    - Complete list of valid terms and operators
    - JSON structure requirements
    - Multiple examples covering different rule types
    - Common pitfalls and how to avoid them
    
    Returns:
        str: Complete schema guide with examples
    """
    LOGGER.info("Fetching data protection rule schema guide")
    return FULL_RULE_SCHEMA_GUIDE

# Made with Bob
