---
name: curate-glossary
description: >
  Use when the user wants to work on their glossary — including adding or updating definitions,
  translations, regulation-based classification, enrich glossary terms, classify terms by regulation,
  or any other glossary curation task. Trigger phrases include: "I want to work on my glossary",
  "add definitions", "update definitions", "translate my glossary", "enrich glossary terms",
  "classify terms", "regulation-based classification", "classify terms by regulation",
  "glossary updates", "definition updates", "I want to curate my glossary".
---

# About This Skill

This skill guides the user through an interactive, step-by-step workflow for curating glossary
terms from IBM Knowledge Catalog. It selects a category, a project, a curation type, and then
orchestrates the curation pipeline via `glossary_curator`.

## Execution Rules

- **Ignore out-of-scope requests during the flow.** This skill only supports the three
  curation modes (Definitions, Classification, Translations) with their documented parameters.
  If the user asks for anything not covered by these steps (e.g. "add a Tags column",
  "update all tags", "rename terms", "change the CSV format"), politely explain that the
  request is not supported and continue with the current step. Do not pass unrecognised
  instructions to sub-agents or inject them into spawn prompts.
- **Never call `ask_followup_question` more than once in a single turn.** Each turn may
  contain at most one `ask_followup_question` call. If you need to both resolve data (e.g.
  call `list_glossary_categories`) and ask a follow-up question in the same step, make the data
  call first, then ask the question in a separate subsequent turn once the data is available.
- **Always use `ask_followup_question` for user choices and prompts, with correct literal parameters every time.** Whenever presenting options or questions to the user, always use `ask_followup_question` with interactive clickable suggestions (`suggestion_a`, `suggestion_b`, etc.) rather than plain text lists or numbered prompts. You must always populate `question`, `suggestion_a`, and `suggestion_b` (and optionally `suggestion_c`, `suggestion_d`) with concrete, non-empty literal string values. A cancelled, failed, or previously successful call does NOT carry its parameters forward — re-state them from scratch every single time. **Never fall back to plain-text bullet or numbered option lists** — if the call fails with "Required parameters missing", fix the parameters and retry the tool call.
- **Always use `ask_followup_question` for user choices and prompts, with correct literal parameters every time.** Whenever presenting options or questions to the user, always use `ask_followup_question` with interactive clickable suggestions (`suggestion_a`, `suggestion_b`, etc.) rather than plain text lists or numbered prompts. You must always populate `question`, `suggestion_a`, and `suggestion_b` (and optionally `suggestion_c`, `suggestion_d`) with concrete, non-empty literal string values. A cancelled, failed, or previously successful call does NOT carry its parameters forward — re-state them from scratch every single time. **Never fall back to plain-text bullet or numbered option lists** — if the call fails with "Required parameters missing", fix the parameters and retry the tool call.
- **Never call the same tool twice in parallel**, EXCEPT for `spawn_subagent`. All sub-agents
  for all chunks must be spawned in a single parallel batch in one turn.
- **Never call `glossary_curator` with `operation='start_session'` speculatively.** Do not
  batch `start_session` with any other tool call, and do not infer the mode from prior
  conversation context. `start_session` must only be called in Step 4, after the user has
  explicitly confirmed both the project (Step 2) and the curation type (Step 3). Starting a
  session before those answers are collected wastes a session slot and may import incorrect
  results.
- **Tool call failures.** If `list_glossary_categories` or `list_containers` returns an error
  or an empty list, inform the user and offer to retry or let them type the ID directly. Do
  not silently proceed with a null or missing value.

## Curate and Import

### Intro Message

**Before doing anything else**, greet the user with a short, friendly plain-language message.
Keep it simple — one short paragraph.

Example (adapt the wording naturally):

> I'm going to help you curate your glossary. I'll walk you through a few
> quick steps — first we'll pick the category hierarchy, project, and curation
> type, then I'll spawn parallel sub-agents to process the terms. Once they're
> done the results are either shown as a preview or imported directly into
> the catalog, depending on your choice.
>
> **Let's start by choosing a category hierarchy. Note all sub-categories under this category are automatically included.**

After printing this message, immediately proceed to Step 1.

---

### Step 1 — Select a Category Hierarchy

**Fast-path:** if the user has provided a category name (full or partial) or
ID at any point before this step (including the original request or a prior
reply), call `list_glossary_categories`, resolve it to a `category_id`, and
proceed directly to Step 2 — do not ask any questions. If the input partially
matches multiple categories, do not skip — display the matching rows and ask
the user to confirm before proceeding.

Otherwise, ask the user whether they know their category hierarchy using
`ask_followup_question`:

```
question     : "**Step 1 of 3 — Category**\nDo you know which root or parent category you'd like to curate?"
suggestion_a : "Yes — I will type the full name, part of the name, or the ID"
suggestion_b : "No — show me the full list"
```

**If the user knows their category (suggestion_a):**

Ask them to type the category name (full or partial) or the `category_id` UUID.

💡 **Tip:** If multiple categories share the same or very similar names, providing the `category_id` UUID directly avoids any ambiguity.

Then call `list_glossary_categories` and search the returned list:

- **Exact name match** → confirm the category name in chat (reminding that
  all sub-categories under it are included) and proceed to Step 2.
- **Partial name match** → display only the matching rows and ask the user to confirm.
- **UUID match** → match directly on `category_id`, confirm the name in chat
  (reminding that all sub-categories under it are included) and proceed to Step 2.
- **No match** → tell the user no category was found for that input and ask them
  to try again or choose to see the full list.

**If the user does not know their category (suggestion_b):**

Call `list_glossary_categories`. If the call fails or returns an empty list, inform the user
and offer to retry or let them type a `category_id` UUID directly.

Otherwise, **display a flat, alphabetically sorted table directly in chat**.

Sort all categories by `name` (case-insensitive, A → Z). Assign a sequential row number (`#`)
to each. The `category_id` is **never displayed** but is retained internally.

Table columns: `#` | `Category Name`

Display **20 rows per page**. Show rows 1–20 then prompt:

> Showing 1–20 of {{total}}. Reply with a **number** or **name** to select, type **more** to
> see the next 20, or type a keyword to search.

If the total is ≤ 20 display all rows at once without a paging prompt.

**Responding to user replies:**

- **Keyword** → filter the full list (case-insensitive substring match) and reprint matches.
  If none match, say so and reprint the full list from page 1.
- **Number or exact name** → confirm the chosen category name in chat and proceed to Step 2.
- **Ambiguous name** → show matching rows only and ask the user to confirm.

---

### Step 2 — Select a Target Project

After the category is confirmed, ask the user which project the curation
session files should be stored in.

**Fast-path:** if the user has provided a project name (full or partial) or
ID at any point before this step (including the original request or a prior
reply), call `list_containers` (projects), resolve it to a `project_id`, and
proceed directly to Step 3 — do not ask any questions. If the input partially
matches multiple projects, do not skip — display the matching rows and ask
the user to confirm before proceeding. **The fast-path only applies to input
that is clearly a project reference and is distinct from the category name
already resolved in Step 1. Do not re-use the category resolution input as a
project hint.**

Otherwise, ask the user whether they know their project using
`ask_followup_question`:

```
question     : "**Step 2 of 3 — Project**\nWhich IKC project should the curation session be stored in?"
suggestion_a : "Yes — I will type the full name, part of the name, or the ID"
suggestion_b : "No — show me the full list"
```

**If the user knows their project (suggestion_a):**

Ask them to type the project name (full or partial) or the `project_id` UUID. Then call
`list_containers` (projects) and search the returned list:

- **Exact name match** → confirm the project name in chat and proceed to Step 3.
- **Partial name match** → display only the matching rows and ask the user to confirm.
- **UUID match** → match directly on `project_id`, confirm the name in chat and proceed to Step 3.
- **No match** → tell the user no project was found for that input and ask them to try again
  or choose to see the full list.

**If the user does not know their project (suggestion_b):**

Call `list_containers` (projects). If the call fails or returns an empty list, inform the user
and offer to retry or let them type a `project_id` UUID directly.

Otherwise, **display a flat, alphabetically sorted table directly in chat**.

Sort all projects by `name` (case-insensitive, A → Z). Assign a sequential row number (`#`)
to each. The `project_id` is **never displayed** but is retained internally.

Table columns: `#` | `Project Name`

Display **20 rows per page**. Show rows 1–20 then prompt:

> Showing 1–20 of {{total}}. Reply with a **number** or **name** to select, type **more** to
> see the next 20, or type a keyword to search.

If the total is ≤ 20 display all rows at once without a paging prompt.

**Responding to user replies:**

- **Keyword** → filter the full list (case-insensitive substring match) and reprint matches.
  If none match, say so and reprint the full list from page 1.
- **Number or exact name** → confirm the chosen project name in chat and proceed to Step 3.
- **Ambiguous name** → show matching rows only and ask the user to confirm.

---

### Step 3 — Select a Curation Type

After the project is confirmed, display this tip **before** presenting the curation type choices:

💡 **Tip:** For the best results, make sure your terms already have definitions. Running **Definitions** first improves the quality of both Classification and Translation outputs — the AI uses the definitions as context when generating suggestions.

Then present the three curation types via `ask_followup_question`:

```
question     : "**Step 3 of 3 — Curation Type**\nWhat would you like to do with the terms in '{{category name}}'?"
suggestion_a : "Definitions — create missing or new definitions"
suggestion_b : "Classification — assign regulation-based classifications"
suggestion_c : "Translations — translate term names and definitions into another language"
```

Map the user's reply to the `glossary_curator` mode by matching the keyword in their response:

| Keyword in reply | Mode | Notes |
|---|---|---|
| "Definitions" | `definition` | Collect sub-steps below |
| "Classification" | `classification` | Assemble `classification_prompt` from the Classification Mode Prompts section and retain for Step 4 |
| "Translations" | `translation` | Collect languages in sub-step below; assemble `translation_prompt` from the Translation Mode Prompts section and retain for Step 4 |

If the user's reply does not match any of these keywords, ask them to clarify by repeating the `ask_followup_question` with the same options.

**Classification disclaimer (mode = `classification` only):**

Immediately after the user selects Classification, display this notice before proceeding:

> ⚠️ **Important:** These classifications are AI-generated suggestions based on the regulation
> mapping you confirm below. They are not legally binding and must be validated by your
> organization's compliance or legal team.

**Classification sub-steps (mode = `classification` only):**

Before starting the sub-steps, display this orientation banner in chat:

> 🗂️ **Classification setup — 4 quick steps before curation starts:**
> Step A: Confirm your IKC classifications
> Step B: Choose the regulation
> Step C: Review and confirm the mapping
> Step D: Assemble the prompt → then hand off to Step 4

**Step A (1/4) — Confirm the out-of-the-box IKC classifications.**

Display the following hardcoded list of out-of-the-box IKC classifications in chat:

> 📋 **Out-of-the-box IKC classifications:**
>
> | # | Name |
> |---|------|
> | 1 | Personal Information |
> | 2 | Personally Identifiable Information |
> | 3 | Sensitive Personal Information |
> | 4 | Confidential |

Then immediately call `ask_followup_question`:

```
question     : "Do any of these classification names differ from what's in your IKC catalog?"
suggestion_a : "✅ All correct — these match my IKC"
suggestion_b : "✏️ One or more names are different in my IKC"
```

**If the user selects suggestion_a (✅ All correct):**

Set `classification_labels` to the default list and proceed to Step B:

```
classification_labels = ["Personal Information", "Personally Identifiable Information", "Sensitive Personal Information", "Confidential"]
```

**If the user selects suggestion_b (✏️ Names differ):**

Ask the user to type corrections in the format `number=ExactName` (e.g. `1=Personal Data, 3=Restricted`):

```
question     : "Type each correction as number=ExactName (e.g. 1=Personal Data, 3=Restricted). Use the exact names from your IKC catalog UI."
suggestion_a : "I'll type my corrections now"
```

Parse the reply, update the corresponding entries in `classification_labels`, display the updated list in chat, then proceed to Step B.

**Step B (2/4) — Ask which regulation applies.**

```
question     : "Which regulation or standard should I use to guide these classifications?"
suggestion_a : "I'll type a regulation or standard name (e.g. GDPR, HIPAA, PCI-DSS, ISO 27001)"
```

Accept the typed value directly as the regulation value. Do not validate it here.

**Step C (3/4) — Infer classification names and propose a mapping.**

Using your knowledge of the regulation or standard the user provided in Step B, infer the
classification Regulation-Classification names that regulation defines. For example:
- GDPR → Personal Data, Special Category Data
- HIPAA → Protected Health Information (PHI), Sensitive Health Information (SHI)
- PCI-DSS → Cardholder Data (CHD), Sensitive Authentication Data (SAD)
- ISO 27001 → Internal, Confidential (or Public / Internal / Confidential / Restricted depending on the organisation's scheme)

If you do not recognise the typed value as a regulation or standard with a formal data
classification scheme, do NOT propose a mapping. Tell the user you have no knowledge of
that regulation or standard and ask them to correct the name and try again.
Do not show the mapping table or present Option A/B until the user provides a recognised
name.

Before building the mapping table, determine how many classification tiers the regulation
defines based on your knowledge. There is no fixed limit — a regulation may have 1, 2, 3,
4, or more tiers. Build one row per tier. Do NOT ask a separate tier-boundary question
before the disclaimer — all tier claims come from training memory and must go through the
Confirm/Correct gate.

**The agent proposes the full mapping — the user does not rank or assign labels.**
For each Regulation-Classification, propose:
1. The Regulation-Classification name (from your knowledge of the pubished or released regulation)
2. The best-matching IKC-Classification from `classification_labels` (retained from Step A),
   selected by name-matching and semantic similarity
3. A concise "When to apply" description — a plain-language sentence explaining what kind
   of term content triggers this classification (from your knowledge of the regulation tier)

Examples:
- GDPR "Personal Data" → IKC `"Personal Information"` → *"Term relates to any data that identifies or can identify a living individual"*
- GDPR "Special Category Data" → IKC `"Sensitive Personal Information"` → *"Term relates to health, biometric, racial origin, political opinions, or other Art. 9 categories"*
- ISO 27001 "Confidential" → IKC `"ISO-Confidential"` → *"Term relates to information whose unauthorised disclosure could cause significant harm to the organisation"*

Only include IKC-Classifications from `classification_labels` in the IKC-Classification column —
do not invent label names. If no IKC-Classification is a reasonable match, show
`"— (no matching IKC-Classification)"` and flag it for the user.

If the number of Regulation-Classifications differs from the number of IKC-Classifications:
- **More IKC-Classifications than Regulation-Classifications:** only map the labels that
  match Regulation-Classifications. List unused IKC-Classifications below the table:
  > *The following IKC-Classifications were not mapped to any {{regulation}} tier and will
  > not be assigned during curation: {{unused label 1}}, {{unused label 2}}, ...*
- **More Regulation-Classifications than IKC-Classifications:** flag the gap before the disclaimer:
  > ⚠️ **{{regulation}}** defines {{m}} tiers but your IKC only has {{n}} matching
  > classification(s). You may need to create additional IKC-Classifications (Option B)
  > before proceeding, or confirm the partial mapping if only some tiers apply.

Present the proposed mapping in a 4-column table:

> 🗂️ **Proposed classification mapping for {{regulation}}:**
>
> | # | Regulation-Classification | IKC-Classification | When to apply |
> |---|---|---|---|
> | 1 | {{Regulation-Classification 1}} | {{IKC-Classification 1}} | {{concise description of what term content triggers this}} |
> | 2 | {{Regulation-Classification 2}} | {{IKC-Classification 2}} | {{concise description}} |
> | 3 | {{Regulation-Classification 3}} | {{IKC-Classification 3}} | {{concise description}} |
> | ... | ... | ... | ... |
>
> *(One row per Regulation-Classification, ordered least to most sensitive.
> IKC-Classification column uses only names from your IKC catalog.)*

After presenting the table, display this disclaimer — do not soften or skip it:

> ⚠️ **Important — unverified mapping**
> The Regulation-Classification names, IKC-Classification assignments, and "When to apply"
> descriptions in this table all come from training memory.
> You must check all three columns against the official regulation source before confirming.

Then immediately call `ask_followup_question`:

```
question     : "Have you reviewed the mapping against the official regulation text?"
suggestion_a : "✅ Confirm — all three columns are correct"
suggestion_b : "✏️ Edit — I'll describe what to change in plain text"
```

**If the user selects suggestion_a (✅ Confirm):**

Proceed directly to the Option A / Option B gate below.

**If the user selects suggestion_b (✏️ Edit):**

Ask the user to describe the change in plain text (e.g. *"row 2 IKC label should be Confidential"*, *"remove row 3"*, *"add a row: Special Category Data → Sensitive Personal Information → Term relates to health data"*):

```
question     : "Describe your correction in plain text. I'll apply it and show you the updated table."
suggestion_a : "I'll type my correction now"
```

Apply the described change, redisplay the full updated mapping table and the unverified disclaimer, then repeat the `ask_followup_question` above. Repeat until suggestion_a (Confirm) is selected.

Once the user selects Confirm (suggestion_a), present Option A / Option B using
`ask_followup_question`:

```
question     : "Ready to proceed. How would you like to continue?"
suggestion_a : "✅ Option A — Use this mapping. Start curation with these IKC-Classifications."
suggestion_b : "🔧 Option B — My IKC classifications need different names. I'll create or rename them first."
```

**Option A — User confirms the mapping:**

Proceed to Step D.

**Option B — User wants to create or rename IKC classifications:**

> ⚠️ Renaming existing labels may affect already-classified terms — check before changing.
> Go to your IKC catalog, make the changes, then return here.

```
question     : "Ready to continue?"
suggestion_a : "✅ Done — I've updated my IKC classifications"
```

Do NOT call `start_session` until suggestion_a is selected. On confirm, return to Step A.

**Step D (4/4) — Assemble the prompt.**

Assemble the `classification_prompt` string from the **Classification Mode Prompts** section
below. Make one substitution:

1. Replace `{classification_mapping_table}` with a markdown table built from the confirmed
   mapping in Step C. Format it exactly as:

   ```
   | Regulation-Classification | IKC-Classification | When to apply |
   |---|---|---|
   | <Regulation-Classification 1> | <IKC-Classification 1> | <When to apply description 1> |
   | <Regulation-Classification 2> | <IKC-Classification 2> | <When to apply description 2> |
   | ... | ... | ... |
   ```

   For GDPR example:
   ```
   | Regulation-Classification | IKC-Classification | When to apply |
   |---|---|---|
   | Personal Data | Personal Information | Term relates to any data that identifies or can identify a living individual |
   | Special Category Data | Sensitive Personal Information | Term relates to health, biometric, racial origin, political opinions, or other Art. 9 categories |
   ```

The fully assembled string must not contain the literal characters `{classification_mapping_table}`.
Retain the assembled `classification_prompt` for Step 4.

**Definition sub-steps (mode = `definition` only):**

First, display this style example table in chat, then ask writing style via `ask_followup_question`:

| Style | Example — "Reporting Date" |
|---|---|
| **Concise** | The specific calendar date on which data is compiled and submitted for review. |
| **Standard** | The specific calendar date on which financial or regulatory data is compiled and recorded as final. It serves as the reference point for reports submitted to stakeholders or regulators. |
| **Verbose** | The specific calendar date on which financial, operational, or regulatory data is compiled and recorded as final. It is used as the reference point for management reports, regulatory filings, and performance dashboards. Reporting Dates are typically governed by internal policies or external regulatory schedules. |

```
question     : "How would you like the definitions written for {{category name}}?"
suggestion_a : "Concise"
suggestion_b : "Standard"
suggestion_c : "Verbose"
```

If the user does not answer this question (e.g. cancels or skips), default to `standard` and inform the user: *"Defaulting to Standard style."*

After the user selects a style, assemble the full `definition_prompt` string from the **Definition Mode Prompts**
section below. Use the outer template and replace `<style_prompt>` with the selected style block:

- **Concise** → use the **Concise Style Block**
- **Standard** → use the **Standard Style Block**
- **Verbose** → use the **Verbose Style Block**

Retain the assembled `definition_prompt` string and the `definition_scope` value for Step 4.

Then ask scope:

```
question     : "Should I create definitions for all terms, or only the ones that don't have one yet?"
suggestion_a : "All terms — generate definitions for every term"
suggestion_b : "Blanks only — only generate definitions for terms that currently have no definition"
```

Map to `definition_scope`: `all` or `blanks_only`. Retain both values for Step 4.
If the user does not answer this question (e.g. cancels or skips), default to `all` and inform the user: *"Defaulting to all terms."*

**Translation sub-steps (mode = `translation` only):**

**Generate a language list at runtime** based on your own knowledge of which languages you
translate at the **highest level of proficiency**. Include dialect and locale variants where
they produce meaningfully different vocabulary, spelling, or phrasing — for example:
English (US), English (UK), English (Australia); French (France), French (Canada);
Spanish (Spain), Spanish (Latin America); Portuguese (Brazil), Portuguese (Portugal);
Chinese (Simplified), Chinese (Traditional). Apply the same principle to any other language
that has meaningful regional variants. Only add a dialect if it produces genuinely different
output — do not add variants just to pad the list.

Order alphabetically by base language name, with dialect variants grouped together immediately
after the base language.

Display the generated table in chat under the heading **"Languages I'm proficient in"**,
formatted as a plain markdown table with a single `Language` column (no row numbers).

Then ask for the target language via `ask_followup_question` (keep prompt concise):

```
question     : "Select target language. Which language should I translate the terms into?"
suggestion_a : "Select from the list above — type the language name"
suggestion_b : "My language isn't listed — I'll type it now"
```

Ask only for the **target language** (required). Do **not** ask for or specify a source language —
the LLM will detect and translate from whatever language the terms are written in.

**Dialect disambiguation:** if the user replies with a bare base language name (e.g. "French")
and two or more dialect variants exist in the list (e.g. French (France), French (Canada)),
use `ask_followup_question` to present the matching dialects as buttons — one per
`suggestion_*` option — and ask the user to confirm which dialect they want. Only trigger
this when the user types the bare base name; if they type a full variant name (e.g.
"French (Canada)") or a name that unambiguously matches a single entry, select it directly.

**Free-typed language confirmation:** if the user types a language name that was not in the
displayed list (i.e. they chose `suggestion_b`), confirm it back before proceeding:

> I'll translate into **{{language}}** — is that correct?

If the name looks ambiguous or possibly misspelled (e.g. "Manderin", "Chineese"), gently
flag it: *"I don't recognise '{{input}}' — did you mean **{{closest match}}**?"* and ask
them to confirm or correct it before retaining it as `target_language`.

Once the target language is confirmed, assemble the `translation_prompt` string from the
**Translation Mode Prompts** section below. Substitute:
- Replace `{target_language}` with the user-selected target language value

Retain the assembled `translation_prompt` for Step 4. Do **not** pass `target_language`
directly to `start_session` — pass `translation_prompt` instead.

---

### Step 4 — Start the Curation Session

**Before presenting the run options, display a human-readable pre-run summary** of the chosen
parameters so the user can see exactly what is about to run. Format it as a clean markdown
block — no raw IDs, no internal field names, no technical jargon.

Use this template, filling in the resolved values:

---
> **Ready to start curation — here's what I'll do:**
>
> | | |
> |---|---|
> | **Category** | `<category_name>` |
> | **Project** | `<project_name>` |
> | **Mode** | `<human-readable mode label>` |
> | **Run type** | `Preview (sample only — no import)` or `Full run (imports into catalog)` |
> | **Style** | `<Concise / Standard / Verbose>` *(Definitions mode only — omit for other modes)* |
> | **Scope** | `<All terms / Blanks only>` *(Definitions mode only — omit for other modes)* |
> | **Target language** | `<language>` *(Translation mode only — omit for other modes)* |
---

For **Classification mode only**, display the assembled prompt as a separate block
immediately after the summary table — before the run type question:

> 📋 **Assembled classification prompt — please review before confirming:**
>
> ```
> <assembled classification_prompt text with all placeholders fully substituted>
> ```
>
> This is the exact instruction the background workers will use to classify your terms.
> If the mapping looks wrong, select **Change curation options** below to go back
> and correct it.

Do NOT show this block for `definition` or `translation` modes.

Display labels for each field:

- **Mode**: use the human-readable label (`Definitions`, `Classification`, or `Translations`) — never the raw mode string.
- **Run type**: on the first display, before the user has chosen, omit this row. Once the user has chosen (e.g. after returning via "Change curation options"), display `Preview (sample only — no import)` or `Full run (imports into catalog)`.
- **Style**: use `Concise`, `Standard`, or `Verbose` — never the raw value (e.g. never `concise`).
- **Scope**: use `All terms` (for `all`) or `Blanks only` (for `blanks_only`) — never the raw value.
- **Target language**: use the full language name as the user confirmed it (e.g. `French (Canada)`).
- Omit **Style** and **Scope** rows entirely for `classification` and `translation` modes.
- Omit the **Target language** row entirely for `definition` and `classification` modes.
- Never display `category_id`, `project_id`, session IDs, or any UUID in this summary.

Then ask the user to choose using `ask_followup_question`:

```
question     : "Everything look good? How would you like to run this curation?"
suggestion_a : "Preview — process the first ~50 terms only; results shown here, nothing imported"
suggestion_b : "Full run — process all terms and import results into the catalog"
suggestion_c : "Change curation options"
suggestion_d : "Quit"
```

- `suggestion_a` → set `run_type = "preview"`, proceed to call `glossary_curator` with `operation="start_session"`.
- `suggestion_b` → set `run_type = "full"`, proceed to call `glossary_curator` with `operation="start_session"`.
- `suggestion_c` → return to Step 3 to re-select the curation type (retaining the already-confirmed category and project) before returning to Step 4 and displaying the updated summary again.
- `suggestion_d` → cancellation flow.

Only call `glossary_curator` with `operation="start_session"` after the user has selected a run type (`suggestion_a` or `suggestion_b`).

Then call `glossary_curator` with `operation="start_session"`, passing:

- `start.category_identifier` — from Step 1
- `project_identifier` — from Step 2
- `start.mode` — from Step 3
- `start.run_type` — from the user's choice above. Always pass this explicitly; never omit it or rely on the server default.

Pass additional parameters based on mode. Do not pass `chunk_size` — leave it at the server
default of 50 terms per chunk.

- **`definition`** — pass `definition_prompt` (assembled in Step 3) and `definition_scope`.
- **`classification`** — pass `classification_prompt` (assembled in Step 3).
- **`translation`** — pass `translation_prompt` (assembled in Step 3).

**Error: draft terms blocking** — if `start_session` returns `error_type: "draft_terms_present"`,
resolve each category ID in `blocking_categories` to its category name using the category list
from Step 1 (or by calling `list_glossary_categories` if not yet loaded), display both the
Category Name and Category ID along with the draft count in a table, and tell the user:

> Curation is blocked because one or more categories have unpublished draft terms.
> Please publish or discard the draft terms listed below, then try again.

| Category Name | Category ID | Draft Count |
|---|---|---|
| `<category_name>` | `<category_id>` | `<draft_count>` |

Do not proceed until the user confirms they have resolved the drafts.

**Error: no eligible terms** — if `start_session` returns `error_type: "no_eligible_terms"`, inform the user:

> The selected category has no terms eligible for curation. It may be empty,
> or all terms were filtered out by the `blanks_only` scope setting.

Suggest trying a different category, or switching the scope to `all` if `blanks_only` was used.

**Blanks-only note** — if the response contains `scope_skipped_count`, inform the user:

> *`{{scope_skipped_count}}` term(s) already had definitions and were skipped.*

`start_session` returns `session_id` immediately. The session is already `"in_progress"`.
Retain `session_id`, `total_terms`, and `total_chunks` from the response and proceed to Step 5.

---

### Step 5 — Spawn Sub-agents

**CRITICAL — PARALLEL SPAWN:** You MUST emit all `spawn_subagent` tool calls (one per chunk
from 0 to `total_chunks - 1`) **together in a single assistant turn as a parallel batch**.
Do NOT spawn one sub-agent, wait for it to complete, and then spawn the next.

Follow the `orchestrator_instruction` field returned by `start_session` precisely — it
contains the exact spawn instructions including the number of chunks and what each sub-agent
must do. Spawn sub-agents with `fork_context: false`. Each sub-agent description **must
include both `session_id` and `project_identifier`** — `project_identifier` is required by every
`glossary_curator` operation.

**If `orchestrator_instruction` is absent or empty**, stop and display an error to the user —
do not attempt to construct spawn prompts manually. Ask the user to report the session ID so
the issue can be investigated.

After spawning all sub-agents in a single batch, call `session_status` immediately:

```
glossary_curator(operation='session_status', session_id='{session_id}', project_identifier='{project_identifier}')
```

Then call `session_status` again every 30 seconds until `pending_chunks` is empty. On every
poll response, check for a `respawn_instruction` field — if present, follow it verbatim in
the same turn before waiting for the next poll cycle.

If `pending_chunks` is still non-empty after 10 minutes of polling, inform the
user that some chunks appear permanently stuck and suggest checking the sub-agent output
before retrying. When `pending_chunks` is empty:

- **Full run** → proceed to Step 6 (complete session and import).
- **Preview run** → proceed to Step 6 (present preview results; do NOT call `complete_session`).

---

### Step 6 — Complete Session and Present Summary

#### 6a — Full run

Once `session_status` returns `status='ready_for_review'` (at the end of Step 5 polling), print the review summary **exactly once**:

> 📋 **Curation complete and ready for review!**
>
> All {{total_chunks}} chunks ({{total_terms}} terms) have been curated.
> Consolidated review file: `{{review_csv_ref}}`

`review_csv_ref` is returned by `session_status` in the `ready_for_review` response. If the field is absent or null, omit the "Consolidated review file" line entirely — do not show a blank or `null` value.

**Do not repeat this block** if entering Step 6a from the Step 5 polling loop — it was already printed there. However, if entering Step 6a via **resume** (i.e. the session was already `ready_for_review` when loaded in the Resume flow, so Step 5 was never run), **do print this block** — it will not have been shown yet.

Then immediately ask the user how to proceed via `ask_followup_question` **using exactly this wording and order**:

```
question     : "All terms have been curated. How would you like to proceed?"
suggestion_a : "Import — import all curated terms into the catalog"
suggestion_b : "Inspect a subset before importing"
suggestion_c : "Cancel — discard without importing"
```

**Do not reorder, rename, or omit any of these suggestions.**

If the user selects `suggestion_b` (inspect), prompt them to type a chunk number:

> There are {{total_chunks}} chunks (0–{{total_chunks - 1}}). Type the chunk number you'd like to inspect (e.g. `0`).

Validate that the number is between 0 and `total_chunks - 1`. If out of range, ask again. Once a valid chunk number is entered, call `session_status` with the corresponding `chunk_index`:

```
glossary_curator(operation='session_status', session_id='{session_id}', chunk_index={chunk_index}, project_identifier='{project_identifier}')
```

Display the returned `curated_rows` as a table in chat, then ask again via `ask_followup_question`:

```
question     : "Chunk {{chunk_index}} reviewed. What would you like to do?"
suggestion_a : "Import — import all curated terms into the catalog"
suggestion_b : "Inspect another chunk"
suggestion_c : "Cancel — discard without importing"
```

If the user selects `"Inspect another chunk"`, re-present the chunk selection question above.

Only after the user explicitly confirms (`suggestion_a`), the **orchestrator (not a sub-agent)** calls:

```
glossary_curator(operation='complete_session', session_id='{session_id}', project_identifier='{project_identifier}')
```

**Error: pre_csv_missing** — if `complete_session` returns `error_type: "pre_csv_missing"`,
follow the `retry_instructions` field in the response (call `complete_session` again after a
few seconds). This is a transient storage race and resolves on retry. Do not surface it as a
failure to the user.

**Error: any other failure** — if `complete_session` returns any other error, display the
error message to the user and retry once. If the retry also fails, surface it as a failure
and provide the raw error message so the user can report it.

#### Status: `completed` or `import_failed`

> ✅ **Curation and import complete!**

| Metric | Value |
|---|---|
| Category | `<category_name>` |
| Mode | `<mode label>` |
| Total Terms Processed | `<total_terms_processed>` |
| Successfully Imported | `<import_summary.imported>` |
| Failed | `<import_summary.failed>` |
| Skipped | `<import_summary.skipped>` |
| Session ID | `<session_id>` |
| Project URL | `<project_url>` |
| Category URL | `<category_url>` |
| Task URL | `<task_url>` |

Display **Mode** using its human-readable label, not the raw mode string:

| Raw mode | Display label |
|---|---|
| `definition` | Definitions |
| `classification` | Classification |
| `translation` | Translations |

Omit the **Project URL**, **Category URL**, and **Task URL** rows if those fields are absent or null in the
response — do not show a blank or `null` value.

If `failure_details` is non-empty, display it as a table beneath the summary:

| Term Name | Reason | Code |
|---|---|---|
| `<term_name>` | `<reason>` | `<code>` |

Offer to run another curation pass on a different category or mode.

#### Status: `completed_with_blocked_chunks`

Present the import summary table above for the successfully imported terms, then immediately
follow with a blocked-terms notice:

> ⚠️ **Some terms could not be curated after 3 attempts and were skipped.**
>
> - **Blocked chunks:** `<blocked_chunks>` (chunk indices)
> - **Blocked term count:** `<blocked_term_count>`
>
> These terms are permanently excluded from this session's import. To investigate, you can
> inspect each blocked chunk in detail. Would you like me to do that now?

**If the user confirms inspection** (or says yes / proceed), call `session_status` for each
blocked chunk index **in a single parallel batch**:

```
glossary_curator(
  operation='session_status',
  session_id='{session_id}',
  chunk_index=N,
  project_identifier='{project_identifier}'
)
```

For each blocked chunk, display the `pre_curated_rows` as a table showing `Artifact ID` and
`Name` (and any other fields present), and the `respawns` list showing what went wrong on
each attempt (outcome, issues). This lets the user identify which specific terms failed and
why.

**Offering a targeted follow-up run:** After showing the inspection results, offer:

> Would you like to start a targeted follow-up curation session for just these blocked terms?
> I can retry only the `<blocked_term_count>` affected terms once the underlying issue is
> resolved (e.g. after fixing the catalog data or adjusting the curation mode).

If the user confirms, collect the `Artifact ID` values from the blocked chunks' `pre_curated_rows`
and start a new session with `start.artifact_ids` set to that list:

```
glossary_curator(
  operation='start_session',
  start={
    'category_id': '<same_category_id>',
    'mode': '<same_mode>',
    'artifact_ids': ['<id1>', '<id2>', ...]
  },
  project_identifier='{project_identifier}'
)
```

Then re-enter at **Step 5** with the new session. Do NOT start a new task, new chat, or
suggest a handoff — the follow-up runs entirely within the current conversation.

---

#### 6b — Preview run

Do **NOT** call `complete_session` — preview sessions cannot be completed or imported, and the
server will return an error if you try.

Instead, call `session_status` with `chunk_index=0` to retrieve the curated rows for display. This is a data fetch — not a duplicate status check — because passing `chunk_index` returns the curated content for that specific chunk rather than the overall session status:

```
glossary_curator(operation='session_status', session_id='{session_id}', chunk_index=0, project_identifier='{project_identifier}')
```

Display the returned `curated_rows` as a readable table in chat. The columns shown depend on
mode:

- **Definitions** — Term Name, Definition
- **Classification** — Term Name, Classifications
- **Translations** — Term Name, translated Term Name, translated Definition

Then present this message and offer to proceed to a full run:

> ✅ **Preview complete** — here's a sample of what the AI generated for the first
> chunk (~{{terms_count}} terms). The results have **not** been imported into the catalog.
>
> Happy with the output? Start a full run to process all {{total_terms}} terms and import
> them into the catalog.

Ask via `ask_followup_question` **using exactly this wording and order**:

```
question     : "Happy to continue to a full run which will start a new session with these curation parameters?"
suggestion_a : "Yes - curate all my category terms using these parameters"
suggestion_b : "No — I want to run the preview again with different parameters"
suggestion_c : "Quit here"
```

**Do not reorder, rename, or omit any of these suggestions.**

- If the user confirms (`suggestion_a`): discard the current preview `session_id`, retain all parameters from Steps 1–3, set
  `run_type = "full"`, return to the **Step 4 pre-run summary** (do not re-ask Steps 1–3),
  and proceed through the full flow.

- If the user wants to run the preview again with different parameters (`suggestion_b`):
  discard the current preview `session_id`, return to Step 3 to re-select the curation type
  (retaining the already-confirmed category and project), and allow the user to modify
  parameters before re-running.

- If the user declines (`suggestion_c`): acknowledge gracefully and offer to start a fresh
  curation run from Step 1.

---

### Resuming an Interrupted Session

If the user returns after a crash, browser close, or other interruption and wants to resume
a previous curation run, first ask for their `project_identifier` (or note it can be left blank for
local storage), then call:

```
glossary_curator(operation='list_sessions', status_filter='all', project_identifier='{project_identifier}')
```

Display the returned active sessions (`in_progress` or `ready_for_review`) as a table (`session_id`, `category_name`, `mode`, `status`, `progress`, `created_at`) and ask the user to confirm which session to resume. Once confirmed:

- **If session is `ready_for_review`** (all chunks complete, awaiting import): proceed directly to **Step 6 — Complete Session and Present Summary / 6a — Full run** to review results and prompt for catalog import approval.
- **If session is `in_progress`**: call `session_status` to determine remaining chunks and re-enter at **Step 5**.

If no resumable sessions are found, inform the user and offer to start a new curation run from Step 1.

---

### Cancellation

If the user quits or asks to stop at any point before Step 6 completes, acknowledge the
cancellation gracefully:

> No problem — curation cancelled. Let me know whenever you'd like to start again.

If a session was already started (Step 4 was reached), note the `session_id` to the user:

> *Session `{session_id}` was started but not completed. You can reference this ID if you
> need to follow up.*

If sub-agents were already spawned (Step 5 was entered), warn the user:

> ⚠️ Sub-agents may still be running in the background and could submit results after
> cancellation. The session will remain in an incomplete state — do not call
> `complete_session` on it unless you intend to import whatever was collected.

**Preview session declined (Step 6b "Quit here")** — if the user declines after
viewing preview results, no cleanup is required. Preview sessions are intentionally never
completed or imported. Inform the user:

> *Preview session `{session_id}` has been discarded — no terms were imported into the
> catalog.*

Offer to restart the workflow from Step 1.

---

## Definition Mode Prompts

This section contains the complete prompt text for Definition mode curation.
The orchestrator assembles the final `definition_prompt` by substituting the selected
style block into the outer template.

---

### Outer Template

```
Write a new Description for each row based solely on the term Name and the Part Of Terms when populated.
Ignore any existing content in the Description column entirely — do not reuse, paraphrase, or build on it.
The description must be clear, complete, and professional.
Do not begin a definition with the term name itself.
Do not begin a definition with a verb — open with a noun phrase, for example: 'The [noun]…' or 'A [noun]…'.

Writing style:
<style_prompt>

Keep all other columns unchanged.
```

---

### Concise Style Block

```
Write exactly 1 sentence per term.
Answer only: what the term is - its core meaning.
State the core meaning directly — no use cases, no qualifications unless essential to distinguish the term from something similar.
The sentence should be complete and stand alone.
```

---

### Standard Style Block

```
Write 1-2 sentences per term.
First sentence: what the term is - its core meaning.
Second sentence (if needed): its primary business purpose or the context in which it applies.
Include the second sentence only if it adds meaning that the first does not already convey.
```

---

### Verbose Style Block

```
Write 2-3 sentences per term.
First sentence: what the term is - its core meaning.
Second sentence: business context — where and how it is used in this domain.
Third sentence (if genuinely needed): a relevant qualification — a compliance consideration, a technical constraint, a relationship to a related term, or a common distinction that practitioners need to know.
Only include the third sentence if it carries information the first two do not. Do not manufacture content to reach three sentences.
```

---

## Classification Mode Prompts

This section contains the complete prompt text for Classification mode curation.
The orchestrator assembles `classification_prompt` by making one substitution into the
template below (`{classification_mapping_table}`) and passes the fully assembled string
to `start_session` as `classification_prompt`.

`{classification_mapping_table}` — a 3-column markdown table (Regulation-Classification /
IKC-Classification / When to apply) built from the confirmed mapping in Step C and D.

---

### Classification Prompt

```
Classify each term by updating its 'Classifications' column according to {regulation} and the confirmed regulation mapping.
Use the term name, the term description, AND the Part Of Terms (when populated) together to determine the classification.

Apply the following mapping to every row:
{classification_mapping_table}

For each term, identify which "When to apply" description best matches the term content,
then set 'Classifications' to the corresponding IKC-Classification value for that row.
If the term does not clearly match any row in the table, leave 'Classifications' empty.
Use ONLY the exact IKC-Classification strings from the table above. Do not use any other values.
Never use Regulation-Classification names as output values — use only the IKC-Classification column values.
Keep all other columns unchanged.
```

---

## Translation Mode Prompts

This section contains the complete prompt text for Translation mode curation.
The orchestrator assembles `translation_prompt` by substituting `{target_language}`
into the template below, then passes the assembled string to `start_session`.

---

### Translation Prompt Template

```
Translate the Name and Description columns of each row into {target_language}.
Detect the source language of each row independently — the glossary may contain a mix of languages.
If a row is already written in {target_language}, leave it unchanged.
Every translated field must be written ENTIRELY in {target_language} —
no source-language words, no parenthetical source-language annotations, no bilingual output.
If the Description field is empty in the source row, leave it empty — do not generate or invent a description.
Translate the full meaning; do not shorten, summarize, or omit sentences.
Preserve technical terms and proper nouns unchanged.
Keep Artifact Type, Category, and all other columns unchanged.
```
