# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

def trigger_interrupt_with_ui(*_args, **_kwargs):
    """
    Stub version of trigger_interrupt_with_ui that does nothing.
    
    Args:
        *_args: Any positional arguments (ignored)
        **_kwargs: Any keyword arguments (ignored)
        
    Returns:
        str: Returns empty string (no actual interrupt occurs)
    """
    return ""

def analyze_user_intention(user_message: str) -> str:
    """
    Stub version of analyze_user_intention that returns the user message.
    
    Args:
        user_message: The user's message to analyze
        
    Returns:
        str: Returns the user message as-is (stub implementation)
    """
    return user_message