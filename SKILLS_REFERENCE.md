# MCP Skills

This document provides a comprehensive list of all Model Context Protocol (MCP) skills available in the Data Intelligence MCP Server and instructions on how to use them. These skills are modular, reusable capabilities, that will provide AI agents with specialized instructions to perform specific tasks.

## Table of Contents
- [MCP Skills](#mcp-skills)
  - [Table of Contents](#table-of-contents)
  - [Where to Get the Skills](#where-to-get-the-skills)
    - [Option 1: From PyPI Package](#option-1-from-pypi-package)
    - [Option 2: From GitHub Repository](#option-2-from-github-repository)
  - [How to Use MCP Skills](#how-to-use-mcp-skills)
    - [Claude Desktop](#claude-desktop)
    - [IBM BOB](#ibm-bob)
    - [VS Code Copilot](#vs-code-copilot)
  - [Available Skills](#available-skills)
    - [Metadata Onboarding and Enrichment Skill](#metadata-onboarding-and-enrichment-skill)


## Where to Get the Skills

The skills are shipped with the Data Intelligence MCP Server and can be accessed in two ways:

### Option 1: From PyPI Package

If you have installed the MCP server via PyPI:

```bash
pip install ibm-watsonx-data-intelligence-mcp-server
```

You can use the included setup command to copy the skills folder to your desired location:

```bash
wxdi-setup-skills
```

**Skills Location in Package:**
- The skills are bundled with the PyPI package at: `site-packages/skills/`
- After running `wxdi-setup-skills`, you can specify any location to copy them to

### Option 2: From GitHub Repository

You can also download the skills directly from the GitHub repository:

**Repository URL:** [https://github.com/IBM/data-intelligence-mcp-server](https://github.com/IBM/data-intelligence-mcp-server)

**Skills Location:** `skills/` directory in the root of the repository

**How to Download:**

1. **Clone the entire repository:**
   ```bash
   git clone git@github.com:IBM/data-intelligence-mcp-server.git
   ```

2. **Navigate to the skills folder:**
   ```bash
   cd data-intelligence-mcp-server/skills
   ```

3. **Copy the skills folder to your desired location** based on your client requirements (see [How to Use MCP Skills](#how-to-use-mcp-skills) section below)

---

## How to Use MCP Skills

### Claude Desktop

In order to use the Data Intelligence skills with Claude Desktop:

- Navigate to the `Customize` tab in the sidebar of Claude Desktop.

- Click on `Skills` icon

- Click on the `+` button -> `Create Skill` -> `Upload a skill`

- Drag and drop or navigate and open the `SKILL.md` file of the skill you would like to use from the `skills` folder in `data-intelligence-mcp-server`

- The skill is now available to use in the chat.

  - You can invoke the skill by using the `/` command and selecting the skill from the list. Example: `/onboard-and-enrich`

  - Claude will also invoke the skill automatically if it detects that the user is asking a question related to the skill.

### IBM BOB

In order to use the Data Intelligence skills with IBM BOB:

- Copy the `skills` folder located in `data-intelligence-mcp-server` to your `.bob` directory. You can find the `.bob` directory in your workspace in IBM BOB IDE. The following directory structure is expected:
  ```
  .bob/
  |---- skills/
  |     |---- skill 1
  |     |     |---- SKILL.md
  |     |---- skill 2
  |     |     |---- SKILL.md
  |     |---- skill 3
  |     |     |---- SKILL.md
  ...
  ```

- The skill is now available to use in the chat in the `Advanced` mode.

  - You can invoke the skill by sending the `use_skill` command followed by the skill name in the chat. Example: `use_skill onboard-and-enrich`

  - IBM BOB will also invoke the skill automatically if it detects that the user is asking a question related to the skill.

- Ask IBM BOB `"What skills do you have?"` to see the list of available skills.

### VS Code Copilot

In order to use the Data Intelligence skills with VS Code Copilot:

- To use the skill as a project skill, copy the `skills` folder located in `data-intelligence-mcp-server` to your `.github` ot `.agents` directory. You can find the `.github` or `.agents` directory in your workspace in VS Code. The following directory structure is expected:
  ```
  .github/ or .agents/
  |---- skills/
  |     |---- skill 1
  |     |     |---- SKILL.md
  |     |---- skill 2
  |     |     |---- SKILL.md
  |     |---- skill 3
  |     |     |---- SKILL.md
  ...
  ```
  - **NOTE**: The above steps are to use the skill as a project skill limited to your workspace. If you want to use the skill globally as a personal skill, you can copy the `skills` folder to the global directory `~/.copilot/skills` or `~/.agents/skills/`.
- The skill is now available to use in the chat.

  - You can invoke the skill by using the `/` command and selecting the skill from the list. Example: `/onboard-and-enrich`

  - Copilot will also invoke the skill automatically if it detects that the user is asking a question related to the skill.

## Available Skills

### Metadata Onboarding and Enrichment Skill

| Skill Name | Description | Sample Prompts | pypi version | CPD version |
|-----------|-------------|---------------|-------------|-------------|
| onboard-and-enrich | Walks user through executing a metadata onboarding, data cataloging and metadata enrichment workflow starting from project setup to connection configuration to metadata import and finally metadata enrichment | "Onboard our Postgres sales database" or "I want to enrich the data I already imported last week" or "Set up a new project for the Finance team and enrich their IBM DB2 data" | >=0.9.0 | TBD |
