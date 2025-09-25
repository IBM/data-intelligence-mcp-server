# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
Logging utilities and setup functions for the Data Intelligence MCP Server.

This module provides utilities for setting up and configuring logging
with custom formats, traceability, and structured output.
"""

import logging
# Removed unused import: os
import sys
from pathlib import Path
from typing import Optional

from .constants import (
    LOGGING_LEVELS,
    JSON_LOGGING,
    HUMAN_LOGGING,
    LOGGING_LEVEL,
    LOGGING_FORMAT,
    CONTAINER_NAME,
    ENVIRONMENT,
    BUILD_VERSION,
    LOG_FILE_PATH,
    set_parameter_value,
    parameter_values
)
from .filter import LoggingTraceabilityFilter

def setup_logging(
    logger_name: Optional[str] = None,
    log_level: Optional[str] = None,
    log_format: Optional[str] = None,
    log_file_path: Optional[str] = None
) -> logging.Logger:
    """
    Configure logging based on specified parameters.
    
    This function sets up a logger with either human-readable or JSON format,
    includes traceability information, and configures appropriate handlers.
    
    Args:
        logger_name: Name for the logger (defaults to container name from config)
        log_level: Logging level (defaults to config value)
        log_format: Logging format type (defaults to config value)
        log_file_path: File to which logs are written. For stdio mode, this is mandatory
                       as stdio is used by the MCP protocol itself
        
    Returns:
        logging.Logger: Configured logger instance
        
    Raises:
        ValueError: If invalid logging level is specified
    """
    # Set parameter values from environment or defaults
    retrieve_parameters_from_env()
    
    # Use provided values or fall back to configuration
    final_logger_name = logger_name or parameter_values[CONTAINER_NAME]
    final_log_level = log_level or parameter_values[LOGGING_LEVEL]
    final_log_format = log_format or parameter_values[LOGGING_FORMAT]
    final_log_file_path = log_file_path or parameter_values.get(LOG_FILE_PATH)
    
    # Get logger instance
    logger = logging.getLogger(final_logger_name)

    # We don't want to propagate the logger to the root logger
    logger.propagate = False
    
    # Return existing logger if already configured
    if logger.handlers:
        return logger
    
    # Validate logging level
    if final_log_level.upper() not in LOGGING_LEVELS:
        raise ValueError(
            f"Invalid logging level '{final_log_level.upper()}'. "
            f"Supported levels: {list(LOGGING_LEVELS.keys())}"
        )
    
    # Set logger level
    logger.setLevel(LOGGING_LEVELS[final_log_level.upper()])
    
    # Create handler based on configuration
    if final_log_file_path:
        # File logging
        log_path = Path(final_log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ch = logging.FileHandler(log_path)
    else:
        # Console logging
        ch = logging.StreamHandler(sys.stdout)
    
    # Configure formatter based on format type
    if final_log_format == HUMAN_LOGGING:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    elif final_log_format == JSON_LOGGING:
        formatter = logging.Formatter(
            '{"environment": "'
            + parameter_values[ENVIRONMENT]
            + '", "build_version": "'
            + parameter_values[BUILD_VERSION]
            + '", "timestamp": "%(asctime)s", "appname": "%(name)s"'
            + ', "loglevel": "%(levelname)s", "message": "%(message)s"'
            + ', "threadId": "%(thread)d", "thread": "%(threadName)s"'
            + ', "sequence_number": "%(sequence_number)d"'
            + ', "transaction_id": "%(transaction_id)s"'
            + ', "trace_id": "%(trace_id)s"'
            + '", "line": "%(lineno)d", "method_name": "%(funcName)s"'
            + ', "class_name": "%(module)s"'
            + '"}'
        )
        # Add traceability filter for JSON logging
        ch.addFilter(LoggingTraceabilityFilter())
    else:
        # Custom format provided
        formatter = logging.Formatter(final_log_format)
    
    # Set formatter and add handler
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    if final_log_file_path:
        # Add console handler for ERROR and CRITICAL levels
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.ERROR)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (defaults to container name from config)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    return setup_logging(logger_name=name)


def retrieve_parameters_from_env() -> None:
    """
    Get and verify configuration from the environment.
    
    This function reads all configuration parameters from environment variables
    and stores them in the parameter_values dictionary.
    """
    from .constants import DEFAULT_PARAMETERS
    
    for parameter_name in DEFAULT_PARAMETERS.keys():
        set_parameter_value(parameter_name)


# Global logger instance 
LOGGER = setup_logging()
