# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from app.core.registry import service_registry
from app.services.data_protection_rules.models.create_rule import (
    CreateRuleRequest,
    CreateRuleResponse,
)


@service_registry.tool(
        name="data_protection_rules_create_rule",
        description="A sample tool for data_protection_rules."
)
async def create_rule(input: CreateRuleRequest) -> CreateRuleResponse:
    greeting = f"Hello from create_rule, {input.name}!"
    return CreateRuleResponse(message=greeting)
