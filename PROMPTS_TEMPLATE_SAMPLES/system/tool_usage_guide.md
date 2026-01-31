# Data Intelligence Tool Usage Guide

## Table of Contents

- [Description](#description)
- [When to Use](#when-to-use)
- [For MCP Clients with Prompt Support](#for-mcp-clients-with-prompt-support)
- [For MCP Clients without Prompt Support](#for-mcp-clients-without-prompt-support)
  - [Option 1: Generate Current Instructions (Recommended)](#option-1-generate-current-instructions-recommended)
  - [Option 2: Manual Configuration](#option-2-manual-configuration)
- [Service-Specific Instructions](#service-specific-instructions)
- [Example: Claude Desktop](#example-claude-desktop)
- [Example: Custom MCP Client](#example-custom-mcp-client)
- [Keeping Instructions Up-to-Date](#keeping-instructions-up-to-date)
- [Benefits](#benefits)
- [Notes](#notes)

## Description

System-level instructions for using all Data Intelligence MCP tools correctly. This prompt provides workflow rules, tool interaction patterns, and best practices for orchestrating multiple tools to accomplish tasks.

**Purpose**: This is a system-level prompt that should be included in the LLM's system context to help it understand how to properly use and orchestrate the Data Intelligence MCP tools.

## When to Use

- Include this in your MCP client's system prompt configuration
- Use when you want the LLM to understand tool workflows and interaction patterns
- Essential for proper tool orchestration across multiple services

## For MCP Clients with Prompt Support

If your MCP client supports MCP prompts, this prompt is available with name:

```
Prompt Name: "Data Intelligence Tool Usage Guide"
```

The MCP server will provide the complete, up-to-date system instructions from all service manifests.

## For MCP Clients without Prompt Support

If your MCP client doesn't support MCP prompts, you need to manually include the system instructions in your client configuration.

### Option 1: Generate Current Instructions (Recommended)

Run this command to generate the current system instructions:

```bash
python -c "from app.services.system_prompts import tool_usage_guide; print(tool_usage_guide())"
```

Copy the output and add it to your MCP client's system prompt configuration.

### Option 2: Manual Configuration

Add the following to your MCP client's system prompt:

```
# Data Intelligence MCP Server - Tool Usage Guide

This guide provides system-level instructions for using Data Intelligence MCP tools effectively.
Follow these guidelines when orchestrating tools to accomplish user tasks.

[Include the system_instructions from each service's manifest.yaml file]
```

## Example: Claude Desktop

**Claude Desktop** supports MCP prompts through the `prompts/list` and `prompts/get` protocol methods. However, prompts are **user-invoked**, not automatically included as system context.

**To use this system prompt in Claude Desktop:**

1. The prompt will appear in Claude's prompt selector when you connect to the MCP server
2. You need to manually invoke it in your conversation to include the instructions
3. Alternatively, you can copy the generated instructions and paste them into your conversation as context

**Standard Claude Desktop configuration** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "data-intelligence": {
      "command": "ibm-watsonx-data-intelligence-mcp-server",
      "args": ["--transport", "stdio"]
    }
  }
}
```

## Example: Custom MCP Client

For custom MCP clients, include the system prompt when initializing the LLM. This would be client specific, but the example below is for a hypothetical Python client:

```python
from mcp import ClientSession

# Get the system prompt
system_prompt = """
# Data Intelligence MCP Server - Tool Usage Guide

[Paste the generated system instructions here]
"""

# Initialize your LLM with the system prompt
llm = YourLLM(
    system_prompt=system_prompt,
    # ... other configuration
)
```

## Keeping Instructions Up-to-Date

**Important**: The system instructions are generated from service manifest files. When services are updated:

1. **With MCP Prompt Support**: Instructions are automatically updated - no action needed
2. **Without MCP Prompt Support**: Re-generate the instructions using Option 1 above and update your client configuration

## Benefits

Including this system prompt helps the LLM:

- ✅ Understand when to use specific tools
- ✅ Follow correct tool sequencing and workflows
- ✅ Apply best practices for tool orchestration
- ✅ Avoid common mistakes in tool usage
- ✅ Handle complex multi-tool scenarios correctly

