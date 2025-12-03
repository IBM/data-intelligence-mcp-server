# This file has been modified with the assistance of IBM Bob AI tool
import re
from typing import Tuple, Optional, Dict, Any


class CRNValidator:
    """
    IBM Cloud CRN (Cloud Resource Name) Validator

    CRN Format: crn:version:cname:ctype:service-name:region:account-id:resource-id:resource-type:resource

    Based on the provided examples:
    - crn:v1:staging:public:cloud-object-storage:global:a/17d6dd3e6388457eab4535166f2dd38b:f741473f-1c81-4949-8ede-6239e10f4ebf::
    """

    def __init__(self):
        # UUID pattern (with or without hyphens)
        self.uuid_pattern = r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"

        # Version pattern (v + number)
        self.version_pattern = r"^v\d+$"

        # Service name pattern (letters, numbers, hyphens)
        self.service_pattern = r"^[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9]$|^[a-zA-Z0-9]$"

        # Region pattern (letters, numbers, hyphens)
        self.region_pattern = (
            r"^[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9]$|^[a-zA-Z0-9]$|^global$"
        )

        # Account ID pattern (a/ + UUID)
        self.account_pattern = r"^a/[0-9a-fA-F]{32}$"

        # Complete CRN regex pattern
        self.crn_pattern = (
            r"^crn:"  # Literal "crn:"
            r"(v\d+):"  # Version (v1, v2, etc.)
            r"([a-zA-Z0-9\-]+):"  # Cname (staging, production, etc.)
            r"([a-zA-Z0-9\-]+):"  # Ctype (public, private, etc.)
            r"([a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9]|[a-zA-Z0-9]):"  # Service name
            r"([a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9]|[a-zA-Z0-9]|global):"  # Region
            r"(a/[0-9a-fA-F]{32}):"  # Account ID
            r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}):"  # Resource ID (UUID)
            r"([^:]*):"  # Resource type (can be empty)
            r"([^:]*)$"  # Resource (can be empty)
        )

    def validate_crn(
        self, crn: str
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Validate a CRN string and return validation result with details.

        Args:
            crn (str): The CRN string to validate

        Returns:
            Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
                - Boolean indicating if CRN is valid
                - Error message if invalid (None if valid)
                - Dictionary with parsed CRN components if valid (None if invalid)
        """
        if not isinstance(crn, str):
            return False, "CRN must be a string", None

        if not crn:
            return False, "CRN cannot be empty", None

        # Check basic structure (must have exactly 9 colons for 10 segments)
        segments = crn.split(":")
        if len(segments) != 10:
            return (
                False,
                f"CRN must have exactly 10 segments separated by colons, found {len(segments)}",
                None,
            )

        # Use regex to validate and parse
        match = re.match(self.crn_pattern, crn)
        if not match:
            error_msg, _ = self._detailed_validation(crn)
            return False, error_msg, None

        # Extract components
        components = {
            "prefix": "crn",
            "version": match.group(1),
            "cname": match.group(2),
            "ctype": match.group(3),
            "service_name": match.group(4),
            "region": match.group(5),
            "account_id": match.group(6),
            "resource_id": match.group(7),
            "resource_type": match.group(8),
            "resource": match.group(9),
        }

        return True, None, components

    def check_service_name(self, segments: list) -> Optional[str]:
        """
        Validate the service name segment of a CRN.
        
        Args:
            segments (list): List of CRN segments split by ':'
            
        Returns:
            Optional[str]: Error message if invalid, None if valid
        """
        if len(segments) > 4:
            if not segments[4]:
                return "Service name cannot be empty"
            if not re.match(self.service_pattern, segments[4]):
                return f"Invalid service name format: '{segments[4]}'"
        return None
    
    def check_region(self, segments: list) -> Optional[str]:
        """
        Validate the region segment of a CRN.
        
        Args:
            segments (list): List of CRN segments split by ':'
            
        Returns:
            Optional[str]: Error message if invalid, None if valid
        """
        if len(segments) > 5:
            if not segments[5]:
                return "Region cannot be empty"
            if not re.match(self.region_pattern, segments[5]):
                return f"Invalid region format: '{segments[5]}'"
        return None
    
    def check_account_id(self, segments: list) -> Optional[str]:
        """
        Validate the account ID segment of a CRN.
        
        Args:
            segments (list): List of CRN segments split by ':'
            
        Returns:
            Optional[str]: Error message if invalid, None if valid
        """
        if len(segments) > 6:
            if not segments[6]:
                return "Account ID cannot be empty"
            if not re.match(self.account_pattern, segments[6]):
                return f"Account ID must be in format 'a/<32-char-hex>', found '{segments[6]}'"
        return None
            
    def check_resource_id(self, segments: list) -> Optional[str]:
        """
        Validate the resource ID segment of a CRN.
        
        Args:
            segments (list): List of CRN segments split by ':'
            
        Returns:
            Optional[str]: Error message if invalid, None if valid
        """
        if len(segments) > 7:
            if not segments[7]:
                return "Resource ID cannot be empty"
            if not re.match(self.uuid_pattern, segments[7]):
                return f"Resource ID must be a valid UUID, found '{segments[7]}'"
        return None

    def _detailed_validation(self, crn: str) -> Tuple[str, None]:
        """
        Provide detailed validation error messages for invalid CRNs.

        Args:
            crn (str): The CRN string to validate

        Returns:
            Tuple[str, None]: Error message and None for components
        """
        segments = crn.split(":")

        # Check prefix
        if segments[0] != "crn":
            return f"CRN must start with 'crn', found '{segments[0]}'", None

        # Check version
        if len(segments) > 1 and not re.match(self.version_pattern, segments[1]):
            return f"Version must follow 'v<number>' format, found '{segments[1]}'", None

        # Check cname (cloud environment)
        if len(segments) > 2 and not segments[2]:
            return "Cname (cloud environment) cannot be empty", None

        # Check ctype (cloud type)
        if len(segments) > 3 and not segments[3]:
            return "Ctype (cloud type) cannot be empty", None

        # Validate each segment using helper methods
        validation_checks = [
            self.check_service_name,
            self.check_region,
            self.check_account_id,
            self.check_resource_id
        ]
        
        for check in validation_checks:
            error_msg = check(segments)
            if error_msg is not None:
                return error_msg, None

        return "Invalid CRN format", None

    def is_valid_crn(self, crn: str) -> bool:
        """
        Simple boolean check for CRN validity.

        Args:
            crn (str): The CRN string to validate

        Returns:
            bool: True if CRN is valid, False otherwise
        """
        is_valid, _, _ = self.validate_crn(crn)
        return is_valid

    def parse_crn(self, crn: str) -> Optional[Dict[str, Any]]:
        """
        Parse a valid CRN and return its components.

        Args:
            crn (str): The CRN string to parse

        Returns:
            Optional[Dict[str, Any]]: Dictionary with CRN components if valid, None if invalid
        """
        is_valid, _, components = self.validate_crn(crn)
        return components if is_valid else None


def validate_crn(crn: str) -> bool:
    """
    Convenience function to validate a CRN.

    Args:
        crn (str): The CRN string to validate

    Returns:
        bool: True if CRN is valid, False otherwise
    """
    validator = CRNValidator()
    return validator.is_valid_crn(crn)
