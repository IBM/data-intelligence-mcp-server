# HTTPS Server Setup Guide

This guide explains how to configure the Data Intelligence MCP Server to run with HTTPS support after installing via `pip install ibm-watsonx-data-intelligence-mcp-server`.

## Table of Contents

- [Quick Start (Development with Self-Signed Certificates)](#quick-start-development-with-self-signed-certificates)
- [Production Setup](#production-setup)
- [Configuration Options](#configuration-options)

## Overview

The Data Intelligence MCP Server supports HTTPS out of the box and can be configured with both self-signed certificates (for development) and proper certificates (for production). The server automatically switches to port 443 when SSL is enabled and uses strong cipher configurations for security.

## Quick Start (Development with Self-Signed Certificates)

For development and testing purposes, you can quickly set up HTTPS with automatically generated self-signed certificates:

### Method 1: Automatic Certificate Generation

```bash
# Install the server
pip install ibm-watsonx-data-intelligence-mcp-server

# Generate self-signed certificates automatically
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr -subj "/CN=localhost"
openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt
rm server.csr
chmod 600 server.key
chmod 644 server.crt

# Run the server with HTTPS
ibm-watsonx-data-intelligence-mcp-server --transport http --ssl-cert ./server.crt --ssl-key ./server.key
```

### Method 2: Using Environment Variables

```bash
# Set up environment variables
export SSL_CERT_PATH=./server.crt
export SSL_KEY_PATH=./server.key

# Run the server (it will automatically use HTTPS when certificates are configured)
ibm-watsonx-data-intelligence-mcp-server --transport http
```

The server will be available at: `https://localhost:443`

## Production Setup

For production environments, use proper certificates from a Certificate Authority (CA) or your organization's PKI.

### Using CA-Issued Certificates

```bash
# Place your certificates in a secure location
sudo mkdir -p /etc/ssl/mcp-server
sudo cp your-domain.crt /etc/ssl/mcp-server/server.crt
sudo cp your-domain.key /etc/ssl/mcp-server/server.key
sudo chmod 600 /etc/ssl/mcp-server/server.key
sudo chmod 644 /etc/ssl/mcp-server/server.crt

# Run with production certificates
ibm-watsonx-data-intelligence-mcp-serverr \
    --transport http \
    --ssl-cert /etc/ssl/mcp-server/server.crt \
    --ssl-key /etc/ssl/mcp-server/server.key \
    --host 0.0.0.0 \
    --port 443 \
    --di-url https://your-data-intelligence-instance.com
```


### Using Let's Encrypt Certificates

```bash
# Install and configure certbot (varies by OS)
# For Ubuntu/Debian:
sudo apt install certbot

# Generate certificate for your domain
sudo certbot certonly --standalone -d your-domain.com

# Run with Let's Encrypt certificates
ibm-watsonx-data-intelligence-mcp-server \
    --transport http \
    --ssl-cert /etc/letsencrypt/live/your-domain.com/fullchain.pem \
    --ssl-key /etc/letsencrypt/live/your-domain.com/privkey.pem \
    --host 0.0.0.0 \
    --di-url https://your-data-intelligence-instance.com
```

## Configuration Options

### Command Line Arguments

| Argument | Description | Example |
|----------|-------------|---------|
| `--transport` | Set to "http" for HTTPS mode | `--transport http` |
| `--ssl-cert` | Path to SSL certificate file | `--ssl-cert /path/to/server.crt` |
| `--ssl-key` | Path to SSL private key file | `--ssl-key /path/to/server.key` |
| `--host` | Server host address | `--host 0.0.0.0` |
| `--port` | Server port (defaults to 443 with SSL) | `--port 8443` |
| `--di-url` | Data Intelligence service URL | `--di-url https://your-instance.com` |

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Server Configuration
SERVER_TRANSPORT=http
SERVER_HOST=0.0.0.0
SERVER_PORT=443
SSL_CERT_PATH=/path/to/server.crt
SSL_KEY_PATH=/path/to/server.key

# Service Configuration. Set the url accordingly for your environment
DI_SERVICE_URL=https://api.dataplatform.cloud.ibm.com
REQUEST_TIMEOUT_S=30

```

### Complete Example Configuration

```bash
# Create a .env file
cat > .env << EOF
# MCP Server HTTPS Configuration
SERVER_TRANSPORT=http
SERVER_HOST=0.0.0.0
SERVER_PORT=443
SSL_CERT_PATH=./certs/server.crt
SSL_KEY_PATH=./certs/server.key

# Service Configuration (if needed)
DI_SERVICE_URL=https://data-intelligence-instance.com
REQUEST_TIMEOUT_S=30
EOF

# Run the server
ibm-watsonx-data-intelligence-mcp-server
```

