# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
"""Provides tool-specific system prompts to the AI."""
from pathlib import Path

import yaml
import app.services


class PromptsProvider:
    """Loads and provides system prompts from service manifests."""

    def __init__(self):
        self.service_instructions: dict[str, str] = {}
        self._load_service_prompts()

    def _load_service_prompts(self):
        """Loads system_instructions from all service/manifest.yaml files."""
        # Use the same approach as service discovery to get correct path
        services_path = Path(app.services.__path__[0])

        for service_dir in services_path.iterdir():
            if service_dir.is_dir():
                manifest_path = service_dir / "manifest.yaml"
                if manifest_path.exists():
                    with open(manifest_path) as f:
                        manifest = yaml.safe_load(f)

                    if 'system_instructions' in manifest:
                        service_name = manifest.get('service', {}).get('name', service_dir.name)
                        self.service_instructions[service_name] = manifest['system_instructions']

    def get_system_prompt(self) -> str:
        """Gets the complete system prompt including all service instructions."""
        base_prompt = """
# MCP Server System Instructions
You are interacting with an MCP (Model Context Protocol) server.
Each tool belongs to a service, and each service may have specific instructions.
## General Rules
1. Always use tools in the documented order
2. Validate outputs before proceeding
3. Stop immediately on errors
## Service-Specific Instructions
"""
        for service_name, instructions in self.service_instructions.items():
            base_prompt += f"\n### Service: {service_name}\n{instructions}\n"

        return base_prompt

# Singleton instance
_prompts_provider = None

def get_prompts_provider() -> PromptsProvider:
    """Gets the singleton prompts provider instance."""
    global _prompts_provider
    if _prompts_provider is None:
        _prompts_provider = PromptsProvider()
    return _prompts_provider
