# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    kind: Literal["tool"]
    id: str = Field(description="e.g., policy.create_rule")
    handler: str
    input_model: str | None = None
    output_model: str | None = None
    description: str | None = None
    timeout: int | None = None
    cache_ttl: int | None = None


class PromptSpec(BaseModel):
    kind: Literal["prompt"]
    id: str = Field(description="e.g., policy.create_rule.prompt")
    # choose one: handler OR template (Jinja2 path relative to service folder)
    handler: str | None = None
    template: str | None = None
    # NEW: optional Pydantic model for prompt arguments
    args_model: str | None = None
    description: str | None = None


class ResourceSpec(BaseModel):
    kind: Literal["resource"]
    id: str = Field(description="e.g., kb.docs")
    list_handler: str | None = None
    read_handler: str | None = None
    description: str | None = None


Capability = ToolSpec | PromptSpec | ResourceSpec


class ServiceInfo(BaseModel):
    name: str
    description: str | None = None
    base_path: str | None = None


class ServiceConfig(BaseModel):
    backend: dict[str, Any] | None = None
    cache: dict[str, Any] | None = None
    logging: dict[str, Any] | None = None


class ServiceManifest(BaseModel):
    # Support both old and new formats for backward compatibility
    group: str | None = Field(None, description="service namespace (legacy)")
    service: ServiceInfo | None = None
    capabilities: list[Capability]
    config: ServiceConfig | None = None

    @property
    def service_name(self) -> str:
        """Get service name from either new or legacy format"""
        if self.service:
            return self.service.name
        return self.group or "unknown-service"

    @property
    def service_base_path(self) -> str | None:
        """Get base path for relative imports"""
        if self.service:
            return self.service.base_path
        return None
