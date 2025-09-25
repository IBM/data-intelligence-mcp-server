# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
Custom logging filter for adding traceability information to logs.

This module provides a custom logging filter that adds traceability
information such as transaction IDs, trace IDs, and sequence numbers
to log records for better request tracking and debugging.
"""

import logging
from contextvars import ContextVar
from typing import Optional

# Context variables for storing traceability information
transaction_id_var: ContextVar[Optional[str]] = ContextVar("transaction_id", default=None)
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)

def get_transaction_id() -> Optional[str]:
    """
    Retrieve the transaction ID from the ContextVar.
    
    Returns:
        str: The transaction ID if set, None otherwise.
    """
    return transaction_id_var.get()


def get_trace_id() -> Optional[str]:
    """
    Retrieve the trace ID from the ContextVar.
    
    Returns:
        str: The trace ID if set, None otherwise.
    """
    return trace_id_var.get()

def set_transaction_id(transaction_id: str) -> None:
    """
    Set the transaction ID in the ContextVar.
    
    Args:
        transaction_id: The transaction ID to set
    """
    transaction_id_var.set(transaction_id)


def set_trace_id(trace_id: str) -> None:
    """
    Set the trace ID in the ContextVar.
    
    Args:
        trace_id: The trace ID to set
    """
    trace_id_var.set(trace_id)

class LoggingTraceabilityFilter(logging.Filter):
    """
    A custom logging filter for adding traceability information to logs.
    
    This filter adds the following information to each log record:
    - sequence_number: Incremental sequence number for log ordering
    - transaction_id: ID for grouping related operations
    - trace_id: Unique ID for request tracing
    
    Attributes:
        seq (int): A sequence number for the logs.
    """
    
    def __init__(self):
        super().__init__()
        self.seq = 0
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add traceability information to the log record.
        
        Args:
            record: The log record to process
            
        Returns:
            bool: Always True to allow the record to be processed
        """
        record.sequence_number = self.seq
        record.transaction_id = get_transaction_id() or ""
        record.trace_id = get_trace_id() or ""
        
        self.seq += 1
        return True
