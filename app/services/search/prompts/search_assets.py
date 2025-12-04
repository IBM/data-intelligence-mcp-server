# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from app.core.registry import prompt_registry


@prompt_registry.prompt(
    name="Search Assets prompt",
    description="Get guidance on how to search for data assets effectively"
)
def search_guide_prompt(
    search_query: str,
    container_type: str = "catalog"
) -> str:
    """
    Provides guidance on searching for data assets in catalog or project.
    
    This prompt helps users understand how to effectively search for data assets
    and provides a structured approach to finding what they need.
    
    Args:
        search_query: Search term to find assets. Can be a keyword or phrase (e.g., "STOCKS", "customer data"). 
                     The search can find semantically equivalent terms in asset names, descriptions, and metadata.
        container_type: The container type in which to search assets, defaults to catalog. Valid values are: 'catalog' (organization-wide search) or 'project' (project-specific search)
    """
    prompt_content = f"""I need help finding data assets in our catalog. 

Search term: {search_query}
Search scope: {container_type or 'catalog'}

Please help me:
1. Understand what types of assets might match my search term (tables, columns, datasets, etc.)
2. Suggest the best search terms and approach
3. Guide me on using the search_asset tool with the right parameters
4. Explain what information I'll get back and how to use it

Provide clear, actionable guidance to help me find what I need."""

    return prompt_content

