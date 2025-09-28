# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import AnyHttpUrl
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

from app.shared.models.ssl_config import SSLConfig


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

    @property
    def ui_url(self) -> AnyHttpUrl | str | None:
        """
        Dynamically create ui_url based on di_service_url and di_env_mode.
        If di_env_mode is CPD, ui_url equals di_service_url.
        Otherwise, it removes 'api.' prefix from di_service_url if present.
        """
        if not self.di_service_url:
            return None

        if self.di_env_mode == "CPD":
            return self.di_service_url

        # For SaaS or any other mode, remove 'api.' prefix if present
        service_url_str = str(self.di_service_url)
        return service_url_str.replace("api.", "", 1)

    # Saas IAM url
    cloud_iam_url: AnyHttpUrl | str | None = None

    # SSL Configuration (enhanced certificate support)
    ssl_config: SSLConfig = SSLConfig()

    # Backwards compatibility - deprecated, use ssl_config instead
    ssl_verify: bool = True  # Set to False for self-signed certificates

    # MCP Server Settings
    server_host: str = "0.0.0.0"
    server_port: int = 3000
    server_transport: str = "http"  # "http" or "stdio"
    ssl_cert_path: str | None = None  # Path to SSL certificate file
    ssl_key_path: str | None = None   # Path to SSL private key file

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

    def get_auth_config(self) -> dict:
        """Get authentication configuration for the current auth mode."""
        return {
            "mode": self.auth_mode,
            "iam_url": self.auth_iam_url,
            "wkc_service_id": self.auth_wkc_service_id,
            "auto_error": self.auth_auto_error,
        }


settings = Settings()
