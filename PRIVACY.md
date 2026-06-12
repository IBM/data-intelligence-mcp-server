# Privacy Policy

## Overview

The IBM Watsonx Data Intelligence MCP Server ("the Server") facilitates secure communication between Model Context Protocol (MCP) clients and IBM Data Intelligence services. This privacy policy explains our data handling practices.

## Data Collection

### What We Collect

1. **Authentication Credentials**
   - API keys (DI_APIKEY)
   - Usernames (DI_USERNAME for CPD environments)
   - Service URLs (DI_SERVICE_URL)

2. **Operational Logs** (only when LOG_FILE_PATH is configured)
   - Tool execution metadata (tool name, execution time, status)
   - Error messages and context
   - Transaction/trace IDs for request tracking
   - Technical metadata (timestamp, log level, thread info)

### How We Collect Data

- **Environment variables** - Authentication credentials and configuration
- **MCP protocol messages** - Tool invocations and responses
- **HTTP headers** (http transport) or **stdio** (stdio transport) - Client-server communication

**Important:** User queries and data are processed in-memory and transmitted to IBM Data Intelligence but are NOT persisted in local logs.

## Data Usage

The Server uses data solely for:

1. **Authentication** - Validating credentials with IBM Data Intelligence services
2. **Service Operations** - Processing requests and returning results to MCP clients
3. **Operational Logging** - Recording execution metadata when LOG_FILE_PATH is configured

### Data Minimization

- Only collects data necessary for authentication and operations
- No personal information beyond authentication credentials
- No user behavior tracking or profiling
- Transient processing without persistent storage (except optional logs)

## Data Storage and Retention

- **In-Memory Processing**: All data processed transiently during active sessions
- **Local Logs**: Stored only when LOG_FILE_PATH is configured; users control location and retention
- **No Server Database**: The Server maintains no persistent storage of user data
- **IBM Data Intelligence**: Data sent to IBM services follows IBM's data handling policies ([IBM Privacy](https://www.ibm.com/privacy))

## Third-Party Sharing

### IBM Data Intelligence Services

The Server acts as a secure intermediary between MCP clients and IBM Data Intelligence services (SaaS or Cloud Pak for Data). Data transmitted to IBM Data Intelligence includes:

- **Authentication credentials** (API keys, bearer tokens, usernames)
- **Tool invocation requests** (tool names, parameters, user queries)
- **Service responses** (metadata, search results, data intelligence outputs)

**Communication Security:**
- **MCP Client ↔ Server:** Uses stdio (standard input/output) or http transport modes
- **Server ↔ IBM Data Intelligence:** Always uses HTTPS/TLS encryption

All data transmitted to IBM Data Intelligence is encrypted in transit via HTTPS and is subject to IBM's privacy policies and security standards. The Server does not modify, store, or log the content of requests and responses beyond operational metadata (when logging is enabled).

### No Other Third Parties

The Server does not share data with any third parties other than IBM Data Intelligence services. No data is:
- Sold to third parties
- Shared with advertising or analytics networks
- Used for marketing purposes

## Security

### Data Protection

1. **Encryption**
   - Server ↔ IBM Data Intelligence: All communications use HTTPS/TLS encryption
   - Custom SSL certificates supported for CPD environments
   - Secure credential transmission to IBM Data Intelligence

2. **Credential Management**
   - Credentials stored in environment variables or secure configuration (not hardcoded in source code)
   - Processed in-memory only
   - Support for API keys and bearer tokens

3. **Access Controls**
   - Authentication required for all IBM Data Intelligence operations
   - User-level controls enforced by IBM Data Intelligence
   - No unauthorized access to data or services

### User Responsibilities

- Securing their API keys and authentication credentials
- Properly configure environment variables
- Manage log file access and permissions
- Keep Server software updated

## User Control

Users have full control over:
- Logging (enable/disable via LOG_FILE_PATH)
- Log file location and retention policies
- Authentication credentials and their rotation
- Disconnect the Server at any time

## Compliance

The Server supports:
- IBM security and privacy standards
- Industry best practices for data handling
- Secure communication protocols (HTTPS/TLS)

For regulated environments, users should:
- Review [IBM Data Intelligence compliance documentation](https://www.ibm.com/docs/en/cloud-paks/cp-data/5.0.x?topic=administering-security-compliance)
- Review [IBM Cloud compliance programs](https://www.ibm.com/cloud/compliance)
- Implement appropriate access controls
- Configure logging according to compliance requirements

## Policy Updates

Updates to this policy will be:

- Communicated through release notes

## Contact

- **GitHub Issues**: [https://github.com/ibm/data-intelligence-mcp-server/issues](https://github.com/ibm/data-intelligence-mcp-server/issues)
- **Documentation**: [https://github.com/ibm/data-intelligence-mcp-server](https://github.com/ibm/data-intelligence-mcp-server)
- **IBM Privacy**: [https://www.ibm.com/privacy](https://www.ibm.com/privacy)

## License

This Server is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.

---

By using the IBM Watsonx Data Intelligence MCP Server, you acknowledge that you have read and understood this privacy policy.