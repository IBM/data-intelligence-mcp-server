# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""SSL utility functions for HTTP client configuration."""

import ssl
from app.shared.models.ssl_config import SSLConfig, CertificateMode


def get_ssl_verify_setting(ssl_config: SSLConfig, ssl_verify: bool = True) -> bool | str | ssl.SSLContext:
    """
    Get the SSL verification setting for HTTP clients.

    This function provides backwards compatibility while enabling enhanced
    certificate support. If ssl_config is configured, it takes precedence.
    Otherwise, falls back to the legacy ssl_verify boolean setting.

    Args:
        ssl_config: The SSL configuration object
        ssl_verify: Legacy boolean SSL verification setting (for backwards compatibility)

    Returns:
        Union[bool, str, ssl.SSLContext]: SSL verification setting for httpx
    """
    # If SSL config is not default, use the enhanced configuration
    if ssl_config.mode != CertificateMode.SYSTEM_DEFAULT:
        return ssl_config.get_httpx_verify_setting()

    # Backwards compatibility: use the legacy ssl_verify setting
    return ssl_verify


def get_ssl_cert_setting(ssl_config: SSLConfig) -> tuple | None:
    """
    Get the SSL client certificate setting for HTTP clients.

    Args:
        ssl_config: The SSL configuration object

    Returns:
        tuple | None: Client certificate configuration for httpx
    """
    return ssl_config.get_httpx_cert_setting()
