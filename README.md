# Data Intelligence MCP Server

The IBM Data Intelligence MCP Server provides a modular and scalable implementation of the Model Context Protocol (MCP), purpose-built to integrate with IBM Data Intelligence services. It enables secure and extensible interaction between MCP clients and IBM’s data intelligence capabilities.


```mermaid
flowchart LR
    github["data-intelligence-mcp Github"] -- publish --> registry
    registry["PyPi registry"] -- pip install ibm-data-intelligence-mcp-server--> server
    subgraph MCP Host
        client["MCP Client"] <-- MCP/STDIO --> server("Data Intelligence MCP Server")
    end
    server -- HTTPS --> runtime("IBM Data Intelligence")
    subgraph id["Services"]
        runtime
    end
    client <-- MCP/HTTP --> server2("DI MCP Server") -- HTTPS --> runtime

```
---

## Table of Contents

1. [Quick Install - PyPI](#quick-install---pypi)
   - [Prerequisites](#prerequisites)
   - [Installation](#installation)
2. [Server](#server)
   - [HTTP Mode](#http-mode)
   - [HTTPS Mode](#https-mode)
3. [Client Configuration](#client-configuration)
   - [Claude Desktop](#claude-desktop)
     - [stdio (Recommended for local setup)](#stdio-recommended-for-local-setup)
     - [http/https (Remote setup)](#httphttps-remote-setup)
   - [VS Code Copilot](#vs-code-copilot)
     - [stdio (Recommended for local setup)](#stdio-recommended-for-local-setup-1)
     - [http/https (Remote setup)](#httphttps-remote-setup-1)
   - [Watsonx Orchestrate](#watsonx-orchestrate)
4. [Configuration](#configuration)
   - [Client Settings](#client-settings)
   - [SSL/TLS Configuration](#ssltls-configuration)

---

## Quick Install - PyPI

### Prerequisites
- Python 3.11 or higher
- Data Intelligence SaaS or CPD 5.2.1 

### Installation

#### Standard Installation

Use pip/pip3 for standard installation:
```bash
pip install ibm-data-intelligence-mcp-server
```
---

## Server

If you have installed the ibm-data-intelligence-mcp-server locally on your host machine and want to connect from a client such as Claude, Copilot, or LMStudio, you can use the stdio mode as described in the examples under the [Client Configuration](#client-configuration) section.

The server can also be configured and run in http/https mode.

Refer to [Client Settings](#client-settings) section on applicable environment variables for http mode. Update as required before starting the server below. Default DI_ENV_MODE is SaaS

### HTTP Mode
```bash
ibm-data-intelligence-mcp-server --transport http --host 0.0.0.0 --port 3000
```

### HTTPS Mode
Refer to [server_https.md](SERVERS_HTTPS.md) for detailed HTTPS server configuration and setup.

### stdio Mode
When configuring the server through Claude, Copilot, or an MCP client in **stdio mode**, the server does not need to be started separately. The client will invoke the server directly using standard input/output.

---

## Client Configuration

If ibm-data-intelligence-mcp-server is installed on local host machine, then it's recommended to use stdio mode. Use https mode if it has been set up remotely.

### Claude Desktop

#### stdio (Recommended for local setup)
To run the server in stdio mode, make sure server is installed locally using [PyPI](#quick-install---pypi).

Add the MCP server to your Claude Desktop configuration:
```json
{
  "mcpServers": {
    "wxdi-mcp-server": {
      "command": "ibm-data-intelligence-mcp-server",
      "args": ["--transport", "stdio"],
      "env": {
         "DI_SERVICE_URL": "https://api.dataplatform.cloud.ibm.com",
         "DI_APIKEY": "<data intelligence api key>",
         "DI_ENV_MODE": "SaaS",
         "LOG_FILE_PATH": "/tmp/di-mcp-server-logs"
      }
    }
  }
}
```

#### http/https (Remote setup)
If the MCP server is running on a local/remote server in http/https mode.

For Cloud SaaS:
```json
{
  "mcpServers": {
    "wxdi-mcp-server": {
      "url": "<url_to_mcp_server>",
      "type": "http",
      "headers": {
        "x-api-key": "your api key from cloud SaaS"
      }
    }
  }
}
```

For CPD:
```json
{
  "mcpServers": {
    "wxdi-mcp-server": {
      "url": "<url_to_mcp_server>",
      "type": "http",
      "headers": {
        "x-api-key": "your api key from cpd env",
        "username": "<user name from cpd env>"
      }
    }
  }
}
```

### VS Code Copilot

#### stdio (Recommended for local setup)
To run the server in stdio mode, make sure server is installed locally using [PyPI](#quick-install---pypi).

Add the MCP server to your VS Code Copilot MCP configuration:
```json
{
  "servers": {
    "wxdi-mcp-server": {
      "command": "ibm-data-intelligence-mcp-server",
      "args": ["--transport", "stdio"],
      "env": {
         "DI_SERVICE_URL": "https://api.dataplatform.cloud.ibm.com",
         "DI_APIKEY": "<data intelligence api key>",
         "DI_ENV_MODE": "SaaS",
         "LOG_FILE_PATH": "/tmp/di-mcp-server-logs"
      }
    }
  }
}
```

#### http/https (Remote setup)
If the MCP server is running on a local/remote server in http/https mode.

For Cloud SaaS:
```json
{
  "servers": {
    "wxdi-mcp-server": {
      "url": "<url_to_mcp_server>",
      "type": "http",
      "headers": {
        "x-api-key": "your api key from cloud SaaS"
      }
    }
  }
}
```

For CPD:
```json
{
  "servers": {
    "wxdi-mcp-server": {
      "url": "<url_to_mcp_server>",
      "type": "http",
      "headers": {
        "x-api-key": "your api key for cpd env",
        "username": "<user name from cpd env>"
      }
    }
  }
}
```

### Watsonx Orchestrate
**Work in Progress**

---
## Configuration

The MCP server can be configured using environment variables or a `.env` file. Copy `.env.example` to `.env` and modify the values as needed.

### Client Settings

Below client settings are common whether `http` or `stdio` mode

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `DI_SERVICE_URL` | `None` | Base URL for Watsonx Data Intelligence instance. Example: api.dataplatform.cloud.ibm.com for SaaS and cluster url for CPD |
| `DI_ENV_MODE` | `SaaS` | Environment mode (`SaaS` or `CPD`) |
| `REQUEST_TIMEOUT_S` | `60` | HTTP request timeout in seconds |
| `LOG_FILE_PATH` | `None` | Logs will be written here if provided. Mandatory for `stdio` mode |

Below client settings are only applicable for `stdio` mode

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `DI_APIKEY` | `None` | API key for authentication |
| `DI_USERNAME` | `None` | Username (required when using API key for CPD) |
| `DI_AUTH_TOKEN` | `None` | Bearer token for alternative to API key |

For `http/https` mode client can send below headers
| Headers | Default | Description |
|---------------------|---------|-------------|
| `x-api-key` | `None` | API key related to SaaS/CPD |
| `username` | `None` | username for CPD env If API key is provided |
| `authorization` | `None` | Bearer token alternative to apikey |

e.g:

```json
{
  "servers": {
    "wxdi-mcp-server": {
      "url": "<url_to_mcp_server>",
      "type": "http",
      "headers": {
        "x-api-key": "your api key from cloud SaaS/cpd"
      }
    }
  }
}
```

```json
{
  "servers": {
    "wxdi-mcp-server": {
      "url": "<url_to_mcp_server>",
      "type": "http",
      "headers": {
        "authorization": "Bearer token"
      }
    }
  }
}
```


### SSL/TLS Configuration

If running in CPD environment, you might need to configure SSL certificate for client connection. Please look into [SSL_CERTIFICATE_GUIDE.md](SSL_CERTIFICATE_GUIDE.md) for more details.
