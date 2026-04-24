# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
Utility functions for mapping IAM IDs to email addresses in workflow tools.

This module provides centralized functions to convert IAM IDs to user email addresses
with consistent error handling and logging across all workflow tool modules.
"""

from typing import List, Optional
from app.core.auth import get_user_email_from_iam_id
from app.shared.logging import LOGGER


async def convert_iam_id_to_email(iam_id: str, context: str = "user") -> str:
    """
    Convert IAM ID to email address with error handling.
    
    Args:
        iam_id: The IAM ID to convert
        context: Context for logging (e.g., "assignee", "candidate_user", "created_by")
        
    Returns:
        Email address if successful, original IAM ID if conversion fails
    """
    try:
        return await get_user_email_from_iam_id(iam_id)
    except Exception as e:
        LOGGER.debug(f"Failed to get email for {context} {iam_id}: {e}")
        return iam_id


async def process_candidate_users(candidate_users_raw: List[str]) -> Optional[List[str]]:
    """
    Process candidate users list, converting IAM IDs to email addresses.
    
    Args:
        candidate_users_raw: Raw list of IAM IDs
        
    Returns:
        List of email addresses if successful, None if input is None or empty list
    """
    if candidate_users_raw is None:
        return None
    
    if not isinstance(candidate_users_raw, list):
        return candidate_users_raw
    
    if len(candidate_users_raw) == 0:
        return None
    
    processed_users = []
    for iam_id in candidate_users_raw:
        if iam_id:
            email = await convert_iam_id_to_email(iam_id, "candidate_user")
            processed_users.append(email)
    
    return processed_users