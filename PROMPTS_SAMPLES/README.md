# Prompt Samples

This directory contains sample prompts that are available in the MCP server. These samples are provided for reference and for use with MCP clients that don't support prompt registration.

## Available Prompts

### Search Service
- **[Search Assets Prompt](search/search_assets_prompt.md)** - Get guidance on how to search for data assets effectively

### Lineage Service
- **[Lineage Impact Analysis Prompt](lineage/impact_analysis_prompt.md)** - Perform impact analysis using data lineage to understand downstream and upstream dependencies

## Usage

### For MCP Clients with Prompt Support

If your MCP client supports prompt registration, the prompts are automatically available through the MCP server. You can call them by their registered names:
- `Search Assets prompt`
- `Lineage Impact Analysis`

### For MCP Clients without Prompt Support

If your MCP client doesn't support prompt registration, you can:
1. Reference the prompt templates in the respective markdown files
2. Use the templates directly in your application
3. Replace the placeholders with actual values as shown in the usage examples

Each prompt file includes:
- Description of the prompt
- Input parameters with types and descriptions
- The prompt template
- Usage examples with formatted outputs

## Structure

```
PROMPTS_SAMPLES/
├── README.md (this file)
├── search/
│   └── search_assets_prompt.md
└── lineage/
    └── impact_analysis_prompt.md
```

## Notes

- All prompts use placeholders (e.g., `{parameter_name}`) that need to be replaced with actual values
- Optional parameters are clearly marked in the parameter tables
- Default values are specified where applicable
- Each prompt file includes multiple usage examples showing different scenarios

