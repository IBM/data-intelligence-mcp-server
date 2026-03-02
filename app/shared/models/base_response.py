# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.Apache License, Version 2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from typing import Optional


class BaseResponseModel(BaseModel):
    """
    Base response model with standardized error handling fields.
    
    All response models should inherit from this to ensure consistent
    error handling across wxo tools.
    """
    error: Optional[str] = Field(
        default=None, 
        description="Error message if the operation failed"
    )
    success: bool = Field(
        default=True, 
        description="Whether the operation was successful"
    )