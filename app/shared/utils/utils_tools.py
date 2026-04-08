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

def format_dict_for_table(data_dict: dict, field_column_name: str = "Field", value_column_name: str = "Value") -> list:
    """
    Format any dictionary into a table-friendly structure.
    Flattens nested dictionaries and lists into key-value pairs for display.
    Shows ALL fields including those with None values.
    
    Args:
        data_dict: The dictionary to format
        field_column_name: Name for the field/key column (default: "Field")
        value_column_name: Name for the value column (default: "Value")
        
    Returns:
        list: A list of dictionaries suitable for table display
    """
    formatter = _DictTableFormatter(field_column_name, value_column_name)
    return formatter.format(data_dict)


class _DictTableFormatter:
    """Helper class to format dictionaries into table structures."""
    
    def __init__(self, field_column_name: str, value_column_name: str):
        self.field_column_name = field_column_name
        self.value_column_name = value_column_name
        self.formatted_rows = []
    
    def format(self, data_dict: dict) -> list:
        """Format the dictionary and return formatted rows."""
        for key, value in data_dict.items():
            self._process_value(key, value)
        return self.formatted_rows
    
    def _add_row(self, key_path: str, value: str) -> None:
        """Add a formatted row to the results."""
        self.formatted_rows.append({
            self.field_column_name: key_path,
            self.value_column_name: value
        })
    
    def _process_value(self, key_path: str, val) -> None:
        """Process a value and add to formatted_rows, handling nested structures."""
        if isinstance(val, dict):
            self._process_dict(key_path, val)
        elif isinstance(val, list):
            self._process_list(key_path, val)
        else:
            self._process_scalar(key_path, val)
    
    def _process_scalar(self, key_path: str, val) -> None:
        """Process a scalar value."""
        display_value = str(val) if val is not None else "None"
        self._add_row(key_path, display_value)
    
    def _process_dict(self, key_path: str, val: dict) -> None:
        """Process a dictionary value."""
        if not val:
            self._add_row(key_path, "{}")
            return
        
        for sub_key, sub_value in val.items():
            new_path = f"{key_path} > {sub_key}"
            self._process_value(new_path, sub_value)
    
    def _process_list(self, key_path: str, val: list) -> None:
        """Process a list value."""
        if not val:
            self._add_row(key_path, "[]")
            return
        
        if _is_dict_like(val[0]):
            self._process_dict_list(key_path, val)
        else:
            self._add_row(key_path, str(val))
    
    def _process_dict_list(self, key_path: str, val: list) -> None:
        """Process a list of dict-like items."""
        for idx, item in enumerate(val):
            self._process_dict_like_item(key_path, idx, item)
    
    def _process_dict_like_item(self, key_path: str, idx: int, item) -> None:
        """Process a single dict-like item in a list."""
        items_iter = _get_items_iterator(item)
        
        if items_iter is None:
            self._add_row(f"{key_path}[{idx}]", str(item))
            return
        
        self._process_dict_like_item_with_iterator(key_path, idx, item, items_iter)
    
    def _process_dict_like_item_with_iterator(self, key_path: str, idx: int, item, items_iter) -> None:
        """Process dict-like item using its iterator."""
        try:
            for sub_key, sub_value in items_iter:
                sub_key_path = f"{key_path}[{idx}] > {sub_key}"
                self._process_value(sub_key_path, sub_value)
        except (TypeError, AttributeError):
            self._add_row(f"{key_path}[{idx}]", str(item))


def _is_dict_like(item) -> bool:
    """Check if an item is dict-like."""
    return (
        hasattr(item, 'items') or
        hasattr(item, 'keys') or
        isinstance(item, dict)
    )


def _get_items_iterator(item):
    """Get an iterator for dict-like items."""
    if hasattr(item, 'items'):
        return item.items()
    if hasattr(item, 'keys'):
        return ((k, item[k]) for k in item.keys())
    return None
