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

from app.core.registry import prompt_registry


@prompt_registry.prompt(
    name="Generate Glossary Artifact Description",
    description="Generate clear, concise descriptions for glossary artifacts based on metadata"
)
def generate_artifact_description_prompt(
    artifact_type: str,
    artifact_name: str,
    metadata: str = ""
) -> str:
    """
    Provides guidance on generating descriptions for glossary artifacts.
    
    This prompt helps generate professional, informative descriptions for glossary
    artifacts (terms, categories, classifications, etc.) based on their metadata.
    
    Args:
        artifact_type: Type of glossary artifact (e.g., "glossary_term", "category", "classification")
        artifact_name: Name of the artifact to generate description for
        metadata: Optional metadata about the artifact to inform the description
    
    Returns:
        str: The formatted prompt text
    """
    prompt_content = f"""You are an expert data governance analyst. Generate a clear, concise description for a glossary artifact based on the provided metadata.

**Artifact Information:**
* Type: {artifact_type}
* Name: {artifact_name}
{f"* Metadata: {metadata}" if metadata else ""}

**Description Requirements:**
1. Explain what the artifact represents in business terms
2. Describe its purpose and usage
3. Highlight key relationships or properties
4. Be 2-4 sentences long
5. Be written in a professional, informative tone

**Important:**
* Do not include generalized descriptions indicating it was created by AI
* Focus on the most relevant information from the metadata provided
* Use clear, business-friendly language
* Avoid technical jargon unless necessary

Please generate an appropriate description for this glossary artifact."""

    return prompt_content