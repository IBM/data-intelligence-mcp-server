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
    name="Lineage Impact Analysis",
    description="Perform impact analysis using data lineage to understand downstream and upstream dependencies"
)
def lineage_impact_analysis_prompt(
    change: str,
    assets: str,
    technology: str,
    datasources: str,
    direction: str = "downstream",
    depth: str = "3 levels deep",
    target_type: str = ""
) -> str:
    """
    Provides guidance on performing impact analysis using data lineage.
    
    This prompt helps users understand the impact of changes to data assets by analyzing
    lineage relationships and identifying affected downstream or upstream dependencies.
    
    Args:
        change: Describe the change you are about to make (e.g., "Merge columns First Name and Last Name into a column Full Name")
        assets: List affected assets (e.g., "db1.schemaA.myTable.first_name, db1.schemaA.myTable.last_name")
        technology: In which technology are you making the change? (e.g., "PostgreSQL")
        datasources: Within which data sources are the assets you are about to change? (e.g., "DWH")
        direction: In which direction do you want to search for the impacts? (e.g., "downstream / upstream / both")
        depth: How many lineage hops should be considered? (e.g., "immediate dependents only / 3 levels deep / no limit - full lineage")
        target_type: Do you want to filter results with specific asset type? (e.g., "tables, views, reports")
    """
    prompt_content = f"""You are a data lineage and metadata analysis assistant. I will describe a change I plan to make to a data asset (e.g., schema, table, column, view, model, or report). Your task is to analyze the downstream impact — specifically, what other assets, data models, dashboards, or reports depend on it.

**My input:**
* Change description: '{change}'
* Changed asset(s): '{assets}'
* Technology: '{technology}'
* System Name: '{datasources}'
* Direction of analysis: '{direction}'
* Lineage depth level (number of hops): '{depth}'
* Target asset types (filter): '{target_type or "all asset types"}'

**Perform the following steps:**
1. Find the changed asset(s) meeting the specified criteria in the lineage repository and use them as starting nodes for the lineage analysis
2. Perform lineage analysis in the specified direction, using the provided parameters like number of hops
3. Filter the assets found on lineage to only include those matching the specified filter

**Provide the following output:**
* A list of found assets - Asset name, type, path (e.g. database name and schema name of a table), and data source definition name to which the asset belongs
* A simplified (ASCII) data flow diagram showing the dependencies between the changed assets and the assets found when performing the impact analysis
* For each impacted asset, explain how is it impacted, and suggest how can the impact be contained

Please help me understand the full impact of this change and provide actionable recommendations."""

    return prompt_content