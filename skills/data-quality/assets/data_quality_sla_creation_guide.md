# Creating a Data Quality SLA - Quick Guide

## What is a DQ SLA?
A Data Quality SLA monitors data assets and ensures they meet specific quality thresholds.

---

## Step 1: Name the SLA
Choose a descriptive name for the SLA.

**Examples:** "Customer Data Quality SLA", "Banking Data SLA", "Sales Completeness SLA"

---

## Step 2: Choose Asset Selection Method
Pick one of these options:

- **By Business Terms** - Monitor assets tagged with specific business terms
- **By Asset Names** - Monitor specific named assets
- **All Assets** - Monitor all assets without filters

---

## Step 3: Specify Assets (if needed)
Depending on the choice in Step 2:

- **Business Terms**: List the business term names (e.g., "Customer Data", "Financial Records")
- **Asset Names**: List the asset names (e.g., "BANK_CLIENTS", "CUSTOMERS_TABLE")
- **All Assets**: Skip this step

---

## Step 4: Set Quality Thresholds
Choose which quality dimensions to monitor and set minimum percentages (0-100):

**Available Dimensions:**
- `completeness` - All required data is present
- `validity` - Data follows correct formats
- `consistency` - Data is consistent across sources
- `uniqueness` - No duplicate records
- `conformity` - Follows data standards
- `accuracy` - Data values are correct
- `timeliness` - Data is up-to-date
- `homogenity` - Uniform data representation
- `coverage` - Data availability extent

**Examples:**
- Basic: `completeness >= 90%`
- Standard: `completeness >= 95%, validity >= 90%`
- Strict: All dimensions at `100%`

---

## Step 5: Add Description (Optional)
Explain the purpose of this SLA.

**Example:** "Ensures banking data meets regulatory compliance standards"

---

## Step 6: Advanced Options (Optional)

### Child Clauses
Apply specific conditions to certain columns:
- Choose selector type: `column_names` or `business_terms`
- List the columns or terms
- Set quality thresholds for those specific items

### Remediation Actions
Trigger workflows when quality drops:
- Provide workflow ID to execute when SLA fails

---

## Quick Example

```
Name: "Banking Data SLA"
Selection: By Asset Names
Assets: ["BANK_CLIENTS", "BANK_ACCOUNTS"]
Description: "Critical banking data quality monitoring"

Thresholds:
  - completeness: 100%
  - validity: 100%
  - uniqueness: 100%
```

---
