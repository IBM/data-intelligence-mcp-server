---
name : mdi-job-control
description : Use this skill to pause, resume, or cancel a running metadata import (MDI) job run. The skill guides the agent through identifying the correct job, confirming the intended action, and executing it using the pause_resume_or_cancel_mdi_job_run tool.
---

# MDI Job Control Guide

## Overview

Use this skill when the user wants to control the lifecycle of an active metadata import job run — specifically to pause, resume, or cancel it. Detect the user's intent and guide them through the correct action using the `pause_resume_or_cancel_mdi_job_run` tool.

Typical user queries: "Pause my metadata import job", "Resume the import I paused earlier", "Cancel the running MDI job in my project", "Stop the import job for the Finance MDI".

## Phase 0: Intent Detection

- Identify which action the user wants: **pause**, **resume**, or **cancel**.
- Identify which metadata import (MDI) and project the user is referring to.
- If the user's intent is unclear, ask them directly: "Do you want to pause, resume, or cancel the job run?"
- If the action is **cancel**, note that this is **permanent and irreversible** — you must confirm with the user before proceeding (Phase 2).
- If the action is **pause** or **resume**, you can proceed to Phase 1 once the project and MDI are identified.

## Phase 1: Resolve the Project and MDI

<Steps>
<Step>
1. If the user provided a project name in their query, use the `get_container` tool with `container_id_or_name` set to the project name and `container_type` set to "project" to verify it exists. If found, proceed to Step 3. If not found, proceed to Step 2.
</Step>
<Step>
2. If no project name was provided, or the project was not found, use the `list_containers` tool with `container_type` set to "project" to display available projects. Ask the user which project contains their metadata import.
</Step>
<Step>
3. Use the `search_metadata_import` tool with `project_name` set to the confirmed project name and optionally `metadata_import_name` set to the name provided by the user to verify the MDI exists and retrieve its details.
</Step>
<Step>
4. If the MDI is not found, inform the user and ask them to verify the name. You can call `search_metadata_import` without a name to list all MDIs in the project.
</Step>
</Steps>

## Phase 2: Confirm the Action

<Steps>
<Step>
1. For **pause**: Confirm with the user which job run to pause. If no specific `job_run_id` is needed, inform them the latest Running or Queued job run will be targeted automatically.
</Step>
<Step>
2. For **resume**: Confirm with the user which job run to resume. If no specific `job_run_id` is needed, inform them the latest Paused job run will be targeted automatically.
</Step>
<Step>
3. For **cancel**: This action is **permanent and cannot be undone**. Always explicitly confirm with the user before proceeding:
   - State clearly: "Canceling a job run is permanent — it cannot be resumed. Are you sure you want to cancel?"
   - Only proceed once the user confirms.
</Step>
</Steps>

## Phase 3: Execute the Operation

<Steps>
<Step>
1. Call the `pause_resume_or_cancel_mdi_job_run` tool with:
   - `project_name` set to the project name from Phase 1
   - `metadata_import_name` set to the MDI name from Phase 1
   - `action` set to `"pause"`, `"resume"`, or `"cancel"` based on the user's intent
   - `job_run_id` set to a specific run ID only if the user provided one; otherwise omit it
</Step>
<Step>
2. Display the result to the user:
   - Show the confirmation message returned by the tool
   - Show the new job state
   - Show the UI URL so the user can monitor the job
</Step>
<Step>
3. After a **pause**, offer to resume later: "You can resume this job run at any time by asking me to resume it."
</Step>
<Step>
4. After a **cancel**, offer to start fresh: "To start a new import run, ask me to execute the metadata import again."
</Step>
</Steps>

## Error Guidance

| Error | What to do |
|-------|-----------|
| Project not found | Use `list_containers` to show available projects |
| MDI not found | Use `search_metadata_import` without a name to list all MDIs in the project |
| No eligible job run (for pause) | No Running or Queued job found — inform the user and offer to start a new run with `run_metadata_import` |
| No eligible job run (for cancel) | No Running, Paused, or Queued job found — inform the user and offer to start a new run with `run_metadata_import` |
| No paused job run (for resume) | There is no paused job to resume — check if the job is still running or has already completed |
| Job in wrong state | Explain the valid states: pause requires Running or Queued, resume requires Paused, cancel requires Running/Paused/Queued |

---

[//]: # (Copyright [2026] [IBM])
[//]: # (Licensed under the Apache License, Version 2.0 \(http://www.apache.org/licenses/LICENSE-2.0\))
[//]: # (See the LICENSE file in the project root for license information.)
