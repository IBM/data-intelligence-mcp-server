# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI Tool

from pydantic import AnyHttpUrl, field_validator, AliasChoices, Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

from app.shared.models.ssl_config import SSLConfig, CertificateMode

# Environment mode constants for case-insensitive comparisons
ENV_MODE_SAAS = "SAAS"
ENV_MODE_CPD = "CPD"

DEV_CLOUD_DOMAIN = "dev.cloud.ibm.com"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        str_strip_whitespace=True,
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields like old TOKEN setting
        validate_by_name=True,
    )

    @field_validator("di_service_url", mode="before")
    @classmethod
    def strip_slashes(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().strip("/")

    # HTTP Client Settings
    request_timeout_s: int = 60
    di_service_url: AnyHttpUrl | str | None = None
    
    # HTTP Client Connection Pool Settings
    http_max_connections: int = 150  # Max concurrent outgoing connections to external APIs
    http_max_keepalive_connections: int = 50  # Max idle connections kept in pool for reuse
    http_keepalive_expiry: float = 60.0  # Seconds to keep idle connections alive
    
    # Semaphore Settings (Application-level concurrency control)
    ibm_api_max_concurrent_calls: int = 50  # Max concurrent IBM API calls (protects downstream services)
    
    # Retry Settings for Rate Limiting (HTTP 429)
    retry_max_attempts: int = 3  # Maximum number of retry attempts for rate-limited requests
    retry_backoff_base: float = 2.0  # Base for exponential backoff (2^0=1s, 2^1=2s, 2^2=4s, 2^3=8s...)
    
    # Server-side Connection Settings (for HTTP transport mode)
    server_limit_concurrency: int = 300  # Max concurrent incoming client connections
    server_timeout_keep_alive: int = 60  # Keep-alive timeout for client connections (seconds)
    server_backlog: int = 2048  # Connection queue size for pending connections

    # Context for UI URLs (df, cpdaas for SaaS; df, cpd for CPD)
    di_context: str = "df"

    @property
    def valid_contexts(self) -> list[str]:
        """
        Returns the list of valid contexts based on the environment mode.
        For SaaS: df, cpdaas, wx
        For CPD: df, cpd, wx, icp4data
        """
        if self.di_env_mode.upper() == ENV_MODE_CPD:
            return ["df", "cpd", "wx", "icp4data"]
        else:  # SaaS
            return ["df", "cpdaas","wx"]

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
    
    @property
    def resource_controller_url(self) -> AnyHttpUrl | str | None:
        if not self.di_service_url:
            return "https://resource-controller.cloud.ibm.com"
        
        if DEV_CLOUD_DOMAIN in self.di_service_url:
            return "https://resource-controller.test.cloud.ibm.com"
        else:
            return "https://resource-controller.cloud.ibm.com"
        
    @property
    def user_management_url(self) -> AnyHttpUrl | str | None:
        if not self.di_service_url:
            return "https://user-management.cloud.ibm.com"
                
        if DEV_CLOUD_DOMAIN in self.di_service_url:
            return "https://user-management.test.cloud.ibm.com"
        else:
            return "https://user-management.cloud.ibm.com"

    @property
    def accounts_url(self) -> str:
        if self.di_service_url and DEV_CLOUD_DOMAIN in str(self.di_service_url):
            return "https://accounts.test.cloud.ibm.com"
        return "https://accounts.cloud.ibm.com"

    # Saas IAM url
    cloud_iam_url: AnyHttpUrl | str | None = None

    # SSL Configuration (enhanced certificate support)
    ssl_config: SSLConfig = SSLConfig()

    # Flat env-var fields for ssl_config construction (read by pydantic-settings from both
    # os.environ and .env — used in model_post_init instead of os.environ.get())
    ssl_config_mode: str = ""
    ssl_config_ca_bundle_path: str | None = None
    ssl_config_client_cert_path: str | None = None
    ssl_config_client_key_path: str | None = None
    ssl_config_client_key_password: SecretStr | None = None
    ssl_config_check_hostname: bool = True

    def model_post_init(self, __context) -> None:
        """Post-initialization to handle SSL configuration from pydantic-loaded fields."""
        ssl_mode = self.ssl_config_mode.lower()
        if ssl_mode == "disabled":
            self.ssl_config = SSLConfig(mode=CertificateMode.DISABLED)
        elif ssl_mode == "custom_ca_bundle":
            self.ssl_config = SSLConfig(
                mode=CertificateMode.CUSTOM_CA_BUNDLE,
                ca_bundle_path=self.ssl_config_ca_bundle_path,
            )
        elif ssl_mode == "client_cert":
            self.ssl_config = SSLConfig(
                mode=CertificateMode.CLIENT_CERT,
                client_cert_path=self.ssl_config_client_cert_path,
                client_key_path=self.ssl_config_client_key_path,
                client_key_password=(
                    self.ssl_config_client_key_password.get_secret_value()
                    if self.ssl_config_client_key_password is not None
                    else None
                ),
                check_hostname=self.ssl_config_check_hostname,
            )

    # Backwards compatibility - deprecated, use ssl_config instead
    ssl_verify: bool = True  # Set to False for self-signed certificates

    # MCP Server Settings
    server_host: str = "0.0.0.0"
    server_port: int = 3000
    server_transport: str = "http"  # "http" or "stdio"
    ssl_cert_path: str | None = None  # Path to SSL certificate file (mapped from SSL_CERT_PATH)
    ssl_key_path: str | None = None   # Path to SSL private key file (mapped from SSL_KEY_PATH)
    use_https: bool = Field(
        default=True,
        validation_alias=AliasChoices("SERVER_HTTPS", "USE_HTTPS"),
    )

    @field_validator("use_https", mode="before")
    @classmethod
    def coerce_legacy_bool(cls, v: object) -> object:
        """Accept legacy falsy strings used before pydantic-settings migration.

        The old os.environ.get() code accepted "n", "no", "off" as False.
        Pydantic v2's bool coercion does not recognise those values, so we
        normalise them here to preserve backward compatibility.
        """
        if isinstance(v, str) and v.lower() in {"n", "no", "off"}:
            return False
        return v

    # OAuth proxy settings
    oauth_upstream_client_id: str = ""
    oauth_upstream_client_secret: str = ""
    oauth_base_url: str = ""

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

    # experimental tools
    use_experimental: bool = False

    # Tool feature groups to enable (stdio mode only; HTTP mode uses x-tool-groups header).
    # Accepts either a comma-separated string or a JSON array string:
    #   TOOL_GROUPS=data_product,lineage
    #   TOOL_GROUPS=["data_product","lineage"]
    # Valid groups: data_product, metadata_management_and_governance, data_quality,
    #               lineage, generative_ai
    tool_groups: str = ""

settings = Settings()
