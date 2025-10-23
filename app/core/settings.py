# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI Tool

import os
from pydantic import AnyHttpUrl
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

from app.shared.models.ssl_config import SSLConfig, CertificateMode

# Environment mode constants for case-insensitive comparisons
ENV_MODE_SAAS = "SAAS"
ENV_MODE_CPD = "CPD"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields like old TOKEN setting
    )

    # HTTP Client Settings
    request_timeout_s: int = 30
    di_service_url: AnyHttpUrl | str | None = None

    # Context for UI URLs (df, cpdaas for SaaS; df, cpd for CPD)
    di_context: str = "df"

    @property
    def valid_contexts(self) -> list[str]:
        """
        Returns the list of valid contexts based on the environment mode.
        For SaaS: df, cpdaas
        For CPD: df, cpd
        """
        if self.di_env_mode.upper() == ENV_MODE_CPD:
            return ["df", "cpd"]
        else:  # SaaS
            return ["df", "cpdaas"]

    @property
    def ui_url(self) -> AnyHttpUrl | str | None:
        """
        Dynamically create ui_url based on di_service_url and di_env_mode.
        If di_env_mode is CPD, ui_url equals di_service_url.
        Otherwise, it removes 'api.' prefix from di_service_url if present.
        """
        if not self.di_service_url:
            return None

        if self.di_env_mode.upper() == ENV_MODE_CPD:
            return self.di_service_url

        # For SaaS or any other mode, remove 'api.' prefix if present
        service_url_str = str(self.di_service_url)
        return service_url_str.replace("api.", "", 1)

    # Saas IAM url
    cloud_iam_url: AnyHttpUrl | str | None = None

    # SSL Configuration (enhanced certificate support)
    ssl_config: SSLConfig = SSLConfig()

    def model_post_init(self, __context) -> None:
        """Post-initialization to handle environment variable overrides."""
        # Check for SSL_CONFIG_MODE environment variable override
        ssl_mode = os.environ.get("SSL_CONFIG_MODE", "").lower()
        if ssl_mode == "disabled":
            self.ssl_config = SSLConfig(mode=CertificateMode.DISABLED)
        elif ssl_mode == "custom_ca_bundle":
            ca_bundle_path = os.environ.get("SSL_CONFIG_CA_BUNDLE_PATH")
            self.ssl_config = SSLConfig(
                mode=CertificateMode.CUSTOM_CA_BUNDLE,
                ca_bundle_path=ca_bundle_path
            )
        elif ssl_mode == "client_cert":
            self.ssl_config = SSLConfig(
                mode=CertificateMode.CLIENT_CERT,
                client_cert_path=os.environ.get("SSL_CONFIG_CLIENT_CERT_PATH"),
                client_key_path=os.environ.get("SSL_CONFIG_CLIENT_KEY_PATH"),
                client_key_password=os.environ.get("SSL_CONFIG_CLIENT_KEY_PASSWORD"),
                check_hostname=os.environ.get("SSL_CONFIG_CHECK_HOSTNAME", "true").lower() == "true",
            )

        # Check for SERVER_HTTPS environment variable override
        server_https = os.environ.get("SERVER_HTTPS", "True").lower()
        if server_https in ["false", "0", "no", "n", "off"]:
            self.use_https = False

    # Backwards compatibility - deprecated, use ssl_config instead
    ssl_verify: bool = True  # Set to False for self-signed certificates

    # MCP Server Settings
    server_host: str = "0.0.0.0"
    server_port: int = 3000
    server_transport: str = "http"  # "http" or "stdio"
    ssl_cert_path: str | None = os.environ.get("SSL_CERT_PATH")  # Path to SSL certificate file
    ssl_key_path: str | None = os.environ.get("SSL_KEY_PATH")    # Path to SSL private key file
    use_https: bool = True  # Default to HTTPS mode, can be disabled with SERVER_HTTPS=False

    # Auth token for stdio mode (optional)
    di_auth_token: str | None = None

    # Auth apikey for stdio mode(optional)
    di_apikey: str | None = None
    # username for CPD
    di_username: str | None = None

    #CPD, SaaS
    di_env_mode: str = "SaaS"

    # Log file path
    log_file_path: str | None = None

    # wxo compatibile tools
    wxo: bool = False

settings = Settings()
