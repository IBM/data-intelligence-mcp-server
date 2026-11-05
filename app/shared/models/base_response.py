# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.Apache License, Version 2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field  # noqa: I001 # Baseline
from typing import Optional


class BaseResponseModel(BaseModel):
    """
    Base response model with standardized error handling fields.

    All response models should inherit from this to ensure consistent
    error handling across wrapper tools.
    """

    error: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None, description="Error message if the operation failed"
    )
    remediation_steps: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None, description="Guidance on how to handle the error"
    )
    success: bool = Field(
        default=True, description="Whether the operation was successful"
    )
