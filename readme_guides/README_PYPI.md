# Data Intelligence MCP Server

The IBM Data Intelligence MCP Server provides a modular and scalable implementation of the Model Context Protocol (MCP), purpose-built to integrate with IBM Data Intelligence services. It enables secure and extensible interaction between MCP clients and IBM's data intelligence capabilities.

For the list of tools supported in this version and sample prompts, refer to [Tools](https://github.com/IBM/data-intelligence-mcp-server/blob/main/TOOLS_PROMPTS.md).

Resources:
- [Integrating Claude with Watsonx Data Intelligence](https://community.ibm.com/community/user/blogs/ramakanta-samal/2025/10/01/integrating-claude-with-watsonx-data-intelligence) A step-by-step guide showing how Claude Desktop connects to the Data Intelligence MCP Server.
- [Watsonx Orchestrate + Data Intelligence](https://community.ibm.com/community/user/blogs/ramakanta-samal/2025/09/25/data) Demonstrates how Watsonx Orchestrate integrates with the MCP Server for automation.
---
## Quick Install

### Prerequisites
- Python 3.11 or higher
- Data Intelligence SaaS or CPD 5.2.1

### Installation

```bash
pip install ibm-watsonx-data-intelligence-mcp-server
```

Or with uv:

```bash
uvx ibm-watsonx-data-intelligence-mcp-server
```

## Documentation

For complete documentation, including:
- Detailed setup instructions
- Client configuration guides
- Server modes (HTTP, HTTPS, stdio)
- Environment configuration
- SSL/TLS setup
- Available tools and sample prompts

Please visit the [GitHub repository](https://github.com/IBM/data-intelligence-mcp-server).

## Basic Usage

### Run in stdio mode (recommended for local setup)
```bash
uvx ibm-watsonx-data-intelligence-mcp-server --transport stdio
```

### Run in HTTP mode
```bash
ibm-watsonx-data-intelligence-mcp-server --transport http --host 0.0.0.0 --port 3000
```

For more configuration options and detailed instructions, please refer to the [GitHub repository README](https://github.com/IBM/data-intelligence-mcp-server).
