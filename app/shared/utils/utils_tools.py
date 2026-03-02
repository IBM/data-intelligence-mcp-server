# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.services.search.models.container import Container
from app.shared.ui_message.ui_message_context import ui_message_context

def format_connections_or_dsds_for_table(
    connections: list
) -> list:
    from app.services.search.models.search_connection import SearchConnectionResponse
    from app.services.search.models.search_data_source_definition import (
        SearchDataSourceDefinitionResponse,
    )
    
    output = []
    for item in connections:
        info = {
            "Name": item.name if not getattr(item, "url", None)
            else ui_message_context.create_markdown_link(item.url, item.name),
            "Create time": item.create_time,
            "Creator": item.creator_id,
            "Datasource type": item.datasource_type_name,
        }
        if isinstance(item, SearchConnectionResponse):
            info["Container id"] = item.container_id
            info["Container type"] = item.container_type
        output.append(info)
    return output

def format_containers_for_table(containers: list[Container]) -> list:
    return [
        {
            "Name": (
                ui_message_context.create_markdown_link(item.url, item.name) if item.url else item.name
            ),
            "Container": item.type.capitalize(),
        }
        for item in containers
    ]