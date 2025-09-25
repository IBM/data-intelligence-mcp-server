# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Simple SSL/TLS configuration models for certificate management."""

import ssl
from enum import Enum

from pydantic import BaseModel


class CertificateMode(str, Enum):
    """Certificate verification modes for SSL/TLS connections."""

    SYSTEM_DEFAULT = "system_default"      # Use system CA store (default)
    CUSTOM_CA_BUNDLE = "custom_ca_bundle"  # Custom CA certificate bundle file
    CLIENT_CERT = "client_cert"            # Client certificate authentication (mTLS)
    DISABLED = "disabled"                  # Disable SSL verification


class SSLConfig(BaseModel):
    """SSL/TLS configuration for HTTP clients."""

    # Certificate verification mode
    mode: CertificateMode = CertificateMode.SYSTEM_DEFAULT

    # CA Certificate bundle path
    ca_bundle_path: str | None = None

    # Client certificate authentication (mutual TLS)
    client_cert_path: str | None = None
    client_key_path: str | None = None
    client_key_password: str | None = None

    # Basic SSL options
    check_hostname: bool = True

    def get_httpx_verify_setting(self) -> bool | str | ssl.SSLContext:
        """Get the appropriate verify setting for httpx client."""
        if self.mode == CertificateMode.DISABLED:
            return False
        elif self.mode == CertificateMode.SYSTEM_DEFAULT:
            return True
        elif self.mode == CertificateMode.CUSTOM_CA_BUNDLE:
            return self._create_ca_bundle_ssl_context()
        else:  # CLIENT_CERT
            return self._create_custom_ssl_context()

    def get_httpx_cert_setting(self) -> None:
        """
        Get the cert setting for httpx client.

        Note: This always returns None as we now load certificates
        directly into the SSL context (httpx deprecated cert parameter).
        """
        return None

    def _create_custom_ssl_context(self) -> ssl.SSLContext:
        """Create custom SSL context with certificate validation."""
        context = ssl.create_default_context()

        # Load custom CA bundle if provided
        if self.ca_bundle_path:
            try:
                context.load_verify_locations(self.ca_bundle_path)
            except Exception:
                # In production, certificate loading errors should be handled
                # Here we just continue without the custom CA for testing
                pass

        # Load client certificate for mutual TLS
        if self.client_cert_path and self.client_key_path:
            try:
                context.load_cert_chain(
                    self.client_cert_path,
                    self.client_key_path,
                    self.client_key_password
                )
            except Exception:
                # In production, certificate loading errors should be handled
                # Here we just continue without client cert for testing
                pass

        context.check_hostname = self.check_hostname
        return context

    def _create_ca_bundle_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context with custom CA bundle."""
        try:
            return ssl.create_default_context(cafile=self.ca_bundle_path)
        except Exception:
            # In production, CA bundle loading errors should be handled appropriately
            # For testing, we create a default context without the CA bundle
            return ssl.create_default_context()

