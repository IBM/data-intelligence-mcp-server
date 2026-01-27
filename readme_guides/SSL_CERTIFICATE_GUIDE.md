
# SSL Certificate Configuration Guide

This guide explains how to configure SSL certificates for the Data Intelligence MCP Server to securely connect to API endpoints with custom certificate requirements.

## Overview

This MCP server supports multiple SSL certificate verification modes instead of simply disabling SSL verification with `verify=False`. This allows customers to:

- Use custom CA certificate bundles for enterprise environments
- Implement mutual TLS (mTLS) with client certificates
- Accept self-signed certificates in controlled environments
- Maintain backwards compatibility with existing configurations

## Certificate Modes

### 1. System Default (Recommended)
Uses the system's default CA certificate store.

```bash
# Environment variables
SSL_CONFIG_MODE=system_default


### 2. Custom CA Bundle
Use a custom CA certificate bundle file for enterprise environments.

```bash
# Environment variables
SSL_CONFIG_MODE=custom_ca_bundle
SSL_CONFIG_CA_BUNDLE_PATH=/path/to/enterprise-ca-bundle.pem
```


### 3. Client Certificate Authentication (Mutual TLS)
For environments requiring mutual TLS authentication.

```bash
# Environment variables
SSL_CONFIG_MODE=client_cert
SSL_CONFIG_CLIENT_CERT_PATH=/path/to/client.crt
SSL_CONFIG_CLIENT_KEY_PATH=/path/to/client.key
SSL_CONFIG_CLIENT_KEY_PASSWORD=optional_password
SSL_CONFIG_CA_BUNDLE_PATH=/path/to/ca.pem  # Optional custom CA
SSL_CONFIG_CHECK_HOSTNAME=true
```

### 4. Disabled
Disable SSL verification entirely (not recommended for production).

```bash
# Environment variables
SSL_CONFIG_MODE=disabled

# Or Legacy environment variable (still supported)
SSL_VERIFY=false
```

## Configuration Examples

### Enterprise Environment with Custom CA
```bash
# .env file
SSL_CONFIG_MODE=custom_ca_bundle
SSL_CONFIG_CA_BUNDLE_PATH=/etc/ssl/certs/company-ca-bundle.pem
REQUEST_TIMEOUT_S=30
```

### Mutual TLS Setup
```bash
# .env file
SSL_CONFIG_MODE=client_cert
SSL_CONFIG_CLIENT_CERT_PATH=/etc/ssl/client/app.crt
SSL_CONFIG_CLIENT_KEY_PATH=/etc/ssl/client/app.key
SSL_CONFIG_CA_BUNDLE_PATH=/etc/ssl/ca/enterprise-ca.pem
SSL_CONFIG_CHECK_HOSTNAME=true
```

### Development with Self-Signed Certificates
```bash
# .env file for development only
SSL_CONFIG_MODE=disabled
```

## Environment Variable Summary

| Variable | Description | Example |
|----------|-------------|---------|
| `SSL_CONFIG_MODE` | Certificate verification mode | `system_default`, `custom_ca_bundle`, `client_cert`, `disabled` |
| `SSL_CONFIG_CA_BUNDLE_PATH` | Path to CA certificate bundle | `/etc/ssl/certs/ca-bundle.pem` |
| `SSL_CONFIG_CLIENT_CERT_PATH` | Path to client certificate | `/etc/ssl/client.crt` |
| `SSL_CONFIG_CLIENT_KEY_PATH` | Path to client private key | `/etc/ssl/client.key` |
| `SSL_CONFIG_CLIENT_KEY_PASSWORD` | Client key password (optional) | `my_secure_password` |
| `SSL_CONFIG_CHECK_HOSTNAME` | Enable hostname verification | `true`, `false` |
| `SSL_VERIFY` | Legacy SSL verification flag | `true`, `false` (deprecated) |


## Certificate File Requirements

### CA Certificate Files
- **Format**: PEM format
- **Extension**: `.pem`, `.crt`, or `.cer`
- **Content**: One or more CA certificates
- **Permissions**: Readable by the application user

### Client Certificates
- **Certificate File**: PEM format containing the client certificate
- **Private Key File**: PEM format containing the private key
- **Key Permissions**: Restrictive permissions (not world-readable)
- **Password**: Optional password protection for private keys

### Example Certificate Generation

For testing purposes, you can generate self-signed certificates:

```bash
# Generate private key
openssl genrsa -out client.key 2048

# Generate certificate signing request
openssl req -new -key client.key -out client.csr

# Generate self-signed certificate
openssl x509 -req -days 365 -in client.csr -signkey client.key -out client.crt

# Set appropriate permissions
chmod 600 client.key
chmod 644 client.crt
```


## Troubleshooting

### Certificate Loading Errors
If certificates fail to load, the system will:
- Log appropriate error messages
- Fall back to secure defaults when possible
- Continue with reduced functionality rather than crash

Common certificate issues:
- **File not found**: Check that certificate paths are correct and accessible
- **Permission denied**: Ensure the application has read access to certificate files
- **Invalid format**: Verify certificates are in PEM format
- **Expired certificates**: Check certificate expiration dates

### Connection Errors
If SSL connections fail:
- Verify the target server supports the configured SSL/TLS version
- Check that custom CA bundles include the full certificate chain
- Ensure client certificates are properly configured for mutual TLS

### Debugging
Enable debug logging to troubleshoot SSL issues:

```python
import logging
logging.getLogger('httpx').setLevel(logging.DEBUG)
```
