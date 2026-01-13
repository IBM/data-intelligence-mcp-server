# Search Assets Prompt

## Description
Provides guidance on searching for data assets in catalog or project. This prompt helps users understand how to effectively search for data assets and provides a structured approach to finding what they need.

## Prompt Name
`Search Assets prompt`

## Input Parameters

| Parameter | Type | Required | Default | Description | Example |
|-----------|------|----------|---------|-------------|---------|
| `search_query` | string | Yes | - | Search term to find assets. Can be a keyword or phrase. The search can find semantically equivalent terms in asset names, descriptions, and metadata | "STOCKS" |
| `container_type` | string | No | "catalog" | The container type in which to search assets. Valid values: 'catalog' (organization-wide search) or 'project' (project-specific search) | "catalog" or "project" |

## Prompt Template

```
I need help finding data assets in our catalog. 

Search term: {search_query}
Search scope: {container_type}

Please help me:
1. Understand what types of assets might match my search term (tables, columns, datasets, etc.)
2. Suggest the best search terms and approach
3. Guide me on using the search_asset tool with the right parameters
4. Explain what information I'll get back and how to use it

Provide clear, actionable guidance to help me find what I need.
```

## Usage Examples

### Example 1: Simple Search Term in Catalog

**Input:**
- search_query: "STOCKS"
- container_type: "catalog" (or omitted, defaults to "catalog")

**Formatted Prompt:**
```
I need help finding data assets in our catalog. 

Search term: STOCKS
Search scope: catalog

Please help me:
1. Understand what types of assets might match my search term (tables, columns, datasets, etc.)
2. Suggest the best search terms and approach
3. Guide me on using the search_asset tool with the right parameters
4. Explain what information I'll get back and how to use it

Provide clear, actionable guidance to help me find what I need.
```

### Example 2: Search Term in Project

**Input:**
- search_query: "STOCKS"
- container_type: "project"

**Formatted Prompt:**
```
I need help finding data assets in our catalog. 

Search term: STOCKS
Search scope: project

Please help me:
1. Understand what types of assets might match my search term (tables, columns, datasets, etc.)
2. Suggest the best search terms and approach
3. Guide me on using the search_asset tool with the right parameters
4. Explain what information I'll get back and how to use it

Provide clear, actionable guidance to help me find what I need.
```

### Example 3: Multi-word Search Term

**Input:**
- search_query: "customer data"
- container_type: "catalog"

**Formatted Prompt:**
```
I need help finding data assets in our catalog. 

Search term: customer data
Search scope: catalog

Please help me:
1. Understand what types of assets might match my search term (tables, columns, datasets, etc.)
2. Suggest the best search terms and approach
3. Guide me on using the search_asset tool with the right parameters
4. Explain what information I'll get back and how to use it

Provide clear, actionable guidance to help me find what I need.
```

## Notes for MCP Clients

For MCP clients that don't support prompt registration, you can:
1. Use this template directly in your application
2. Replace `{search_query}` with the actual search query
3. Replace `{container_type}` with "catalog" or "project" (defaults to "catalog" if not provided)

