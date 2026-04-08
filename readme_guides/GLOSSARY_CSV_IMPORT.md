# Glossary CSV Import Guide

## Overview

Import business glossary terms and categories from CSV files.

**Key Features:**
- Validation mode (dry-run before import)
- Three merge strategies: `all`, `specified`, `empty`
- Support for categories, terms, and relationships

## MCP Tools

### `get_glossary_csv_schema`
Returns CSV format specification with required/optional columns, allowed values, and examples.

### `glossary_csv_import`
Import or validate glossary artifacts.

**Parameters:**
- `csv_content` (str): CSV content
- `validate_only` (bool): `true` = validate only, `false` = import (default: `false`)
- `merge_option` (str): `all` (default), `specified`, or `empty`

## CSV Format

### Required Columns
- **Name**: Artifact name
- **Artifact Type**: `glossary_term` or `category`

### Common Optional Columns
- **Category**: Parent category (defaults to `[uncategorized]`)
- **Description**: Detailed description
- **Related Terms**: Comma-separated term names
- **Synonyms**: Alternative names
- **Abbreviations**: Short forms

### Example CSV

```csv
Name,Artifact Type,Category,Description,Related Terms,Synonyms
Risk Management,category,[uncategorized],Risk category,,
Credit Risk,glossary_term,Risk Management,Borrower default risk,"PD,LGD",Default Risk
PD,glossary_term,Risk Management,Probability of default,Credit Risk,Probability of Default
```

## Merge Options

- **all** (default): Replace all existing values
- **specified**: Only replace with non-empty imported values
- **empty**: Only fill empty fields

## Import Status Values

- **SUCCEEDED**: Import completed successfully
- **COMPLETED**: Import finished (check for partial success)
- **FAILED**: Import failed (check errors)
- **TIMEOUT**: Import took too long (may still be processing)

## References

- [IBM data intelligence CSV Import](https://dataplatform.cloud.ibm.com/docs/content/wsj/governance/csv-import.html)
- Tool source: `app/services/glossary/tools/glossary_csv_import.py`