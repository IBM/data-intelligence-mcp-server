# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
Logging constants and configuration for the Data Intelligence MCP Server.

This module defines constants used throughout the logging system,
including log levels, formats, and parameter names.
"""

import os
from typing import Dict, Any

# Logging levels mapping
LOGGING_LEVELS = {
    "CRITICAL": 50,
    "ERROR": 40,
    "WARNING": 30,
    "INFO": 20,
    "DEBUG": 10
}

# Logging format types
JSON_LOGGING = "json_logging"
HUMAN_LOGGING = "human_logging"

# Parameter names for configuration
LOGGING_LEVEL = "logging_level"
LOGGING_FORMAT = "logging_format"
CONTAINER_NAME = "container_name"
ENVIRONMENT = "environment"
BUILD_VERSION = "build_version"
LOG_FILE_PATH = "log_file_path"

# Default parameter values
DEFAULT_PARAMETERS = {
    LOGGING_LEVEL: ["INFO", False, str],
    LOGGING_FORMAT: [JSON_LOGGING, False, str],
    CONTAINER_NAME: ["data-intelligence-mcp-server", False, str],
    ENVIRONMENT: ["development", False, str],
    BUILD_VERSION: ["1.0.0", False, str],
    LOG_FILE_PATH: [None, False, str],
}

# Global parameter storage
parameter_values: Dict[str, Any] = {}

def _get_environment_value(parameter_name: str) -> str:
    """
    Get parameter value from environment variable or Pydantic settings.
    
    Args:
        parameter_name: The name of the parameter to look up
        
    Returns:
        str: The environment value if found, None otherwise
    """
    # Try environment variable first
    env_value = os.environ.get(parameter_name.upper())
    
    # Fallback to Pydantic settings if available
    if env_value is None:
        try:
            from app.core.settings import settings
            if hasattr(settings, parameter_name):
                env_value = getattr(settings, parameter_name)
        except ImportError:
            pass
    
    return env_value


def _convert_value_to_type(value: str, param_type: type) -> Any:
    """
    Convert string value to the specified parameter type.
    
    Args:
        value: The string value to convert
        param_type: The target type for conversion
        
    Returns:
        Any: The converted value
    """
    if param_type is bool:
        return value.lower() in ('true', '1', 'yes', 'on')
    elif param_type is int:
        return int(value)
    else:
        return value


def _validate_parameter_exists(parameter_name: str) -> None:
    """
    Validate that the parameter exists in DEFAULT_PARAMETERS.
    
    Args:
        parameter_name: The name of the parameter to validate
        
    Raises:
        ValueError: If parameter is not found in DEFAULT_PARAMETERS
    """
    if parameter_name not in DEFAULT_PARAMETERS:
        raise ValueError(f"Unknown parameter: {parameter_name}")


def _handle_missing_parameter(parameter_name: str, is_mandatory: bool, default_value: Any) -> None:
    """
    Handle the case when parameter value is not found in environment.
    
    Args:
        parameter_name: The name of the parameter
        is_mandatory: Whether the parameter is mandatory
        default_value: The default value to use if not mandatory
        
    Raises:
        ValueError: If parameter is mandatory but not found
    """
    if is_mandatory:
        raise ValueError(f"Required parameter {parameter_name} not found in environment")
    parameter_values[parameter_name] = default_value


def set_parameter_value(parameter_name: str) -> None:
    """
    Set parameter value from environment variable or use default.
    
    Args:
        parameter_name: The name of the parameter to set
    """
    _validate_parameter_exists(parameter_name)
    
    default_value, is_mandatory, param_type = DEFAULT_PARAMETERS[parameter_name]
    env_value = _get_environment_value(parameter_name)
    
    if env_value is not None:
        converted_value = _convert_value_to_type(env_value, param_type)
        parameter_values[parameter_name] = converted_value
    else:
        _handle_missing_parameter(parameter_name, is_mandatory, default_value)
