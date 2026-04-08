# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from fastmcp.server.dependencies import get_http_headers
import json
import jwt
import base64

from app.services.constants import (
    CLOUD_IAM_ENDPOINT,
    CPD_IAM_ENDPOINT,
    AWS_IAM_URL,
    AWS_IAM_TEST_URL,
    AWS_IAM_ENDPOINT,
    AWS_DOMAIN_SUFFIX,
    BEARER_PREFIX,
    JSON_CONTENT_TYPE,
)
from app.shared.exceptions.base import ExternalAPIError

# Application-specific imports
from app.core.settings import settings, ENV_MODE_SAAS, ENV_MODE_CPD
from app.shared.utils.http_client import get_http_client

from aiocache import cached

from app.shared.logging import LOGGER

INVALID_DI_ENV_MODE = "DI_ENV_MODE is either not provided in env or not one of SaaS or CPD"

def get_cloud_iam_url_from_service_url(service_url: str) -> str:
    """
    Calculate the Cloud IAM URL based on the service URL.

    Mapping:
    - https://api.dataplatform.dev.cloud.ibm.com => https://iam.test.cloud.ibm.com
    - https://api.dataplatform.test.cloud.ibm.com => https://iam.cloud.ibm.com
    - https://api.dataplatform.cloud.ibm.com => https://iam.cloud.ibm.com
    - https://api.dev.aws.data.ibm.com => https://account-iam.platform.test.saas.ibm.com (AWS dev)
    - https://api.test.aws.data.ibm.com => https://account-iam.platform.test.saas.ibm.com (AWS test)
    - https://api.*.aws.data.ibm.com => https://account-iam.platform.saas.ibm.com (AWS production regions)

    Args:
        service_url: The service URL to map from

    Returns:
        str: The corresponding Cloud IAM URL
    """
    service_url_str = str(service_url).lower()

    # Check for AWS regions first
    # AWS dev and test environments use the test IAM URL
    if f"dev{AWS_DOMAIN_SUFFIX}" in service_url_str or f"test{AWS_DOMAIN_SUFFIX}" in service_url_str:
        return AWS_IAM_TEST_URL
    # AWS production regions use the production IAM URL
    elif AWS_DOMAIN_SUFFIX in service_url_str:
        return AWS_IAM_URL
    # Standard cloud.ibm.com environments
    elif "dev.cloud.ibm.com" in service_url_str:
        return "https://iam.test.cloud.ibm.com"
    elif "test.cloud.ibm.com" in service_url_str or "cloud.ibm.com" in service_url_str:
        return "https://iam.cloud.ibm.com"
    else:
        return "https://iam.cloud.ibm.com"


async def get_access_token() -> str | None:
    """
    Resolve Authorization header from HTTP request headers or STDIO fallback.
    Returns a full 'Bearer ...' string or None if nothing available.
    If apikey is provided instead, calls relevant apis for SaaS or CPD
    to get the bearer token
    """
    # get_http_headers() never raises exceptions - returns {} if no HTTP context
    headers = get_http_headers()
    
    auth = headers.get("authorization", "")

    if not auth:
        api_key_header = headers.get("x-api-key", "")
        if api_key_header:
            auth = await get_bearer_token_from_apikey(
                api_key_header, headers.get("username", "")
            )

    if not auth and settings.server_transport == "stdio":
        if settings.di_auth_token:
            auth = settings.di_auth_token
            if not auth.lower().startswith("bearer "):
                auth = f"Bearer {auth}"
        elif settings.di_apikey:
            apikey = settings.di_apikey
            username = settings.di_username
            auth = await get_bearer_token_from_apikey(apikey, username)

    return auth or None


def get_iam_url() -> str:
    if settings.di_env_mode.upper() == ENV_MODE_SAAS:
        if settings.cloud_iam_url:
            return settings.cloud_iam_url + CLOUD_IAM_ENDPOINT
        elif settings.di_service_url:
            # Calculate IAM URL dynamically based on service URL
            cloud_iam_url = get_cloud_iam_url_from_service_url(settings.di_service_url)
            service_url_lower = str(settings.di_service_url).lower()
            # Use AWS-specific endpoint for all AWS environments (dev, test, and production)
            if AWS_DOMAIN_SUFFIX in service_url_lower:
                return cloud_iam_url + AWS_IAM_ENDPOINT
            else:
                return cloud_iam_url + CLOUD_IAM_ENDPOINT
        else:
            raise ExternalAPIError("DI_SERVICE_URL is not set in env")
    elif settings.di_env_mode.upper() == ENV_MODE_CPD:
        return settings.di_service_url + CPD_IAM_ENDPOINT
    else:
        raise ExternalAPIError(INVALID_DI_ENV_MODE)


async def get_token() -> str:
    """
    Retrieves the current user token from the context.

    This function checks if a user token is present in the context. If a token is found, it returns ONLY the token as a string without "Bearer ".
    If no token is present, it returns an empty string.

    Returns:
        str: The current user token or an empty string if no token is found.
    """
    access_token = await get_access_token()
    return access_token[7:] if access_token else ""


async def get_bss_account_id() -> str:
    """
    Retrieves the BSS Account ID from the JWT token.

    This function extracts the BSS Account ID from the JWT token by decoding the payload.
    It assumes the token is in a valid format and contains an "account.bss" key.

    Returns:
        str: The BSS Account ID extracted from the token payload.
    """
    if settings.di_env_mode.upper() == ENV_MODE_SAAS:
        token = await get_token()
        
        token_parts = token.split(".")
        
        if len(token_parts) < 2:
            LOGGER.error(f"Invalid JWT token format - expected 3 parts separated by dots, got {len(token_parts)} parts")
            raise ExternalAPIError(f"Invalid JWT token format - token has {len(token_parts)} parts instead of 3")
        
        payload_b64 = token_parts[1]
        # Add padding if needed for base64 decoding
        padding = len(payload_b64) % 4
        if padding:
            payload_b64 += '=' * (4 - padding)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
        return payload.get("account", {}).get("bss", "")
    elif settings.di_env_mode.upper() == ENV_MODE_CPD:
        return "999"
    else:
        raise ExternalAPIError(
            INVALID_DI_ENV_MODE
        )

async def get_user_identifier() -> str:
    """
    Retrieves the user identifier from the JWT token.

    This function extracts the user identifier from the JWT token by decoding the payload.
    For CPD environments, it returns the "uid" field.
    For other environments, it returns the "iam_id" field.

    Returns:
        str: The user identifier extracted from the token payload.
    """
    token = await get_token()
    payload_b64 = token.split(".")[1]
    # Add padding if needed for base64 decoding
    padding = len(payload_b64) % 4
    if padding:
        payload_b64 += '=' * (4 - padding)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))

    if settings.di_env_mode.upper() == ENV_MODE_CPD:
        return payload.get("uid")
    elif settings.di_env_mode.upper() == ENV_MODE_SAAS:
        return payload.get("iam_id")
    else:
        raise ExternalAPIError(
            INVALID_DI_ENV_MODE
        )

def is_aws_environment() -> bool:
    """Check if the current environment is AWS based on the service URL."""
    if settings.di_service_url:
        return AWS_DOMAIN_SUFFIX in str(settings.di_service_url).lower()
    return False


def get_request_body(api_key: str, username: str) -> dict:
    if settings.di_env_mode.upper() == ENV_MODE_SAAS:
        # AWS environments pass only apikey in body
        if is_aws_environment():
            return {
                "apikey": api_key
            }
        # Standard IBM Cloud SaaS includes grant_type
        return {
            "apikey": api_key,
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
        }
    elif settings.di_env_mode.upper() == ENV_MODE_CPD:
        if not username:
            raise ExternalAPIError(
                "For CPD, USERNAME has to be provided in the header if running the server under "
                "http mode else in env if running in stdio mode"
            )
        return {"api_key": api_key, "username": username}
    else:
        raise ExternalAPIError(
            INVALID_DI_ENV_MODE
        )


def get_header() -> dict:
    """
    Get headers for authentication request.
    
    Returns:
        dict: Headers for the authentication request
    """
    if settings.di_env_mode.upper() == ENV_MODE_SAAS:
        # AWS environments use JSON content type
        if is_aws_environment():
            return {
                "Content-Type": JSON_CONTENT_TYPE,
                "accept": JSON_CONTENT_TYPE
            }
        # Standard IBM Cloud SaaS uses form-urlencoded
        return {"Content-Type": "application/x-www-form-urlencoded"}
    elif settings.di_env_mode.upper() == ENV_MODE_CPD:
        return {"Content-Type": JSON_CONTENT_TYPE}
    else:
        raise ExternalAPIError(
            INVALID_DI_ENV_MODE
        )


@cached(ttl=3300)  # 55 minutes - shorter than 1 hour token expiration
async def get_bearer_token_from_apikey(api_key: str, username: str) -> str:

    LOGGER.info("Getting bearer token for the api key passed in")

    headers = get_header()
    req_body = get_request_body(api_key, username)
    iam_url = get_iam_url()

    client = get_http_client()

    try:
        if settings.di_env_mode.upper() == ENV_MODE_SAAS:
            # AWS environments use JSON body and return "token" field
            if is_aws_environment():
                response = await client.post(
                    iam_url,
                    headers=headers,
                    json=req_body
                )
                token = response.get("token", "")
                return BEARER_PREFIX + token
            # Standard IBM Cloud SaaS uses form data and returns "access_token" field
            else:
                response = await client.post(
                    iam_url,
                    headers=headers,
                    data=req_body,
                )
                token = response.get("access_token", "")
                return BEARER_PREFIX + token
        else:
            # CPD uses JSON body and returns "token" field
            response = await client.post(iam_url, headers=headers, json=req_body)
            token = response.get("token", "")
            return BEARER_PREFIX + token

    except ExternalAPIError:
        # This will catch HTTP errors (4xx, 5xx) that were raised by raise_for_status()
        raise
    except Exception as e:
        raise ExternalAPIError(f"Failed to get bearer token: {str(e)}")


@cached(ttl=3300)  # 55 minutes - shorter than 1 hour token expiration
async def get_dph_catalog_id_for_user(bearer_token) -> str:

    LOGGER.info("Getting DPH catalog id")

    headers = get_header()
    headers.update({"Authorization": bearer_token})

    client = get_http_client()

    try:
        response = await client.get(
            f"{settings.di_service_url}/v2/catalogs/ibm-default-hub", headers=headers
        )
        return response.get("metadata", {}).get("guid", "")

    except ExternalAPIError:
        # This will catch HTTP errors (4xx, 5xx) that were raised by raise_for_status()
        raise
    except Exception as e:
        raise ExternalAPIError(f"Failed to get bearer token: {str(e)}")
