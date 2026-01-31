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

"""
System-level prompts that expose service manifest instructions to MCP clients.

This module loads system_instructions from all service manifest.yaml files
and exposes them as an MCP prompt, allowing LLMs to understand tool workflows
and interaction patterns.
"""

from pathlib import Path
from typing import Dict
import yaml

from app.core.registry import prompt_registry


def _load_all_manifests() -> Dict[str, str]:
    """
    Load system_instructions from all service manifest files.
    
    Returns:
        Dictionary mapping service names to their system_instructions
    """
    manifests = {}
    services_dir = Path(__file__).parent
    
    for service_dir in services_dir.iterdir():
        if not service_dir.is_dir() or service_dir.name.startswith('_'):
            continue
            
        manifest_file = service_dir / "manifest.yaml"
        if manifest_file.exists():
            try:
                with open(manifest_file, 'r') as f:
                    manifest = yaml.safe_load(f)
                    
                if manifest and 'system_instructions' in manifest:
                    service_name = manifest.get('service', {}).get('name', service_dir.name)
                    manifests[service_name] = manifest['system_instructions']
            except Exception as e:
                # Log error but continue loading other manifests
                print(f"Warning: Failed to load manifest from {manifest_file}: {e}")
                continue
    
    return manifests


@prompt_registry.prompt(
    name="Data Intelligence Tool Usage Guide",
    description="System-level instructions for using all Data Intelligence MCP tools correctly. "
                "This prompt provides workflow rules, tool interaction patterns, and best practices "
                "for orchestrating multiple tools to accomplish tasks."
)
def tool_usage_guide() -> str:
    """
    Combines all service manifest system_instructions into a single system prompt.
    
    This prompt should be used by MCP clients as part of the system context to help
    LLMs understand:
    - When to use specific tools
    - How tools should be sequenced
    - Tool interaction patterns and workflows
    - Best practices for tool orchestration
    
    Returns:
        Combined system instructions from all service manifests
    """
    manifests = _load_all_manifests()
    
    if not manifests:
        return "No service manifest instructions available."
    
    # Build the combined prompt
    sections = [
        "# Data Intelligence MCP Server - Tool Usage Guide",
        "",
        "This guide provides system-level instructions for using Data Intelligence MCP tools effectively.",
        "Follow these guidelines when orchestrating tools to accomplish user tasks.",
        ""
    ]
    
    # Add each service's instructions
    for service_name, instructions in sorted(manifests.items()):
        sections.append(f"## {service_name.upper().replace('_', ' ')} SERVICE")
        sections.append("")
        sections.append(instructions.strip())
        sections.append("")
    
    return "\n".join(sections)

# Made with Bob
