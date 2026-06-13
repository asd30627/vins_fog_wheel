# OpenSpec Conventions

<!-- TODO: Replace the placeholders in this document with your project description -->

This document defines the conventions for using the OpenSpec tool in **[Project Name]**, including when to use the AI collaboration workflow, spec positioning, naming, and archiving processes.

---

## 0. When to Use the AI Collaboration Workflow

### 0.1 Decision Principle

Before making a modification, ask: **Does this change affect the core content or structure?**

"Core content" includes:
- [TODO: Fill in your project's "core" elements, e.g., section architecture, definitions, requirements]
- [TODO: e.g., security specifications, interface definitions, workflow rules]

### 0.2 Decision Matrix

| Situation | Approach |
|---|---|
| Core content is affected | **Use AI Collaboration Workflow**: explore → propose → apply → archive |
| Core content is NOT affected | **Modify directly** without going through the workflow |

### 0.3 Minimum Obligations for Direct Modification

Bypassing the workflow does not mean leaving no record. When modifying directly, you **must**:

1. Explain "what was changed and why" in the Git commit message
2. If modifying a document → update the corresponding `revision_history.md` (if applicable)

### 0.4 Principle for Gray Areas

If unsure whether core content is affected, **default to using the workflow**.

---

## 0.5 Explore-notes.md Conventions

For every explore session, maintain `explore-notes.md` **unconditionally**:

- If the session is related to a specific change (has a change name) → create or update `openspec/changes/<name>/explore-notes.md`
- If there is no corresponding change → create `openspec/explore-sessions/<YYYY-MM-DD>-<topic>.md` and add an entry under the `## Explore Sessions Log` section in `openspec/engineering-roadmap.md`.

**explore-notes.md Format Requirements**:

```markdown
# Explore Session Notes
**Change**: <name>
**Date**: <YYYY-MM-DD>

## Confirmed Decisions
(Format for each item: ### Dx. <Title> + Decision details)

## Rejected Options (with Reasons)
(Format for each item: ### Xx. <Option Name> + Reason for rejection)

## Future Change Drafts

## Unresolved Issues

## Scope Confirmation for Current Change
```

**Update Timing**: Append immediately after a clear conclusion is reached during the discussion; do not wait until the session ends.

---

## 0.6 Working-Draft.md & Fast-Track Conventions

When an explore session involves creating or modifying document content, create `working-draft.md`:

**File Location:**
- With corresponding change: `openspec/changes/<name>/working-draft.md`
- Without corresponding change: `openspec/explore-sessions/<date>-<topic>-draft.md`

**Maintenance Rules:**

| Item | Rule |
|---|---|
| Trigger Condition | Update immediately after user confirms a section ("Looks good", "Yes", etc.) |
| Update Method | Overwrite directly without keeping historical versions (rely on git history) |
| Format | Exactly identical to the target document format (no discussion context, no TODOs) |
| Unfinished Sections | Do not include in working-draft; list under unresolved issues in explore-notes |
**HARD CONSTRAINT: The Depth Ceiling**
> [!IMPORTANT]  
> The Agent **MUST NEVER** generate publication-ready prose, long paragraphs, or complete schema definitions during the `explore` phase.
> 
> `working-draft.md` is strictly limited to:
> 1. Structural skeletons (Headers, bulleted lists of core concepts)
> 2. Key decisions and technical boundaries
> 
> **Why?** Generating deep content in the `explore` phase breaks the workflow and leaves the `apply` phase with nothing to do. If a draft section reads like a finished document, the Agent has failed this constraint. The Agent must wait until the `apply` phase to expand decisions into polished text.

**Stable Bi-directional Tagging:**
- Add `<!-- Dx -->` at the start of each section in `working-draft.md` to reference the source decision.
- Add a `Draft Link: working-draft#<Heading-Title-or-Anchor>` field to each decision entry in `explore-notes.md`. **Do not use unstable section numbers (like §1.2) for linking.**

**Fast-Track Promotion:**
If the content in `working-draft.md` is complete and locked by the end of the `explore` phase:
1. In the `propose` phase, the generated task description must be formatted as: `[ ] Promote section <Title> from working-draft.md to docs/<filename>.md`
2. In the `apply` phase, the Agent must perform a clean copy/replacement of the draft content into the target document without re-writing or altering the agreed-upon prose.

---

## 0.7 Roadmap & Writing Guide Integration

- **Roadmap (`openspec/engineering-roadmap.md`)**: The single source of truth for planning. It tracks active changes, future backlogs, and explore session histories under the `## Explore Sessions Log` section.
  - When starting a non-change session: Add an entry to the log in `openspec/engineering-roadmap.md` with status "Active".
  - When promoting a session to a change: Move the session notes to `openspec/changes/<change-name>/explore-notes.md` and update the status in the roadmap to `Promoted to <change-name>`.
- **Writing Guide (`openspec/writing_guide.md`)**: Defines style guidelines, Markdown syntax rules, and terminology glossaries. Both the Agent and the human must follow this guide during drafting and proofreading.

---

## 0.8 Skill & Workflow File Management

All skill and workflow files under `.claude/skills/`, `.agent/skills/`, and `.agent/workflows/` are **managed by the project**.

**Synchronized Paths Rule**: When modifying any skill, you must synchronize the changes across these paths:

| Path | Format | Purpose |
|---|---|---|
| `.claude/skills/<skill>/SKILL.md` | Full version | Claude Code (primary execution path) |
| `.agent/skills/<skill>/SKILL.md` | Full version | Antigravity |
| `.agent/workflows/opsx-<skill>.md` | Condensed version | Antigravity workflow |

**Custom Markers**: Wrap custom sections with `<!-- CUSTOM: <Description> -->` tags:

```markdown
<!-- CUSTOM: description -->
...custom content...
<!-- END CUSTOM -->
```

**Upstream Updates**: When pulling latest patches from the `docspec` repository, run `python docspec.py update` to sync to the target project.

---

## 0.9 Living Document & Anti-Append-Only Protocol

1. **User as Ultimate Authority**: The user's latest instruction always overrides any existing content in the files. The files exist to reflect the current consensus, not to dictate it.
2. **Files as Current State, Not Chat Logs**: All output files (`explore-notes.md`, `proposal.md`, `tasks.md`, `working-draft.md`) are mutable states. They must NOT be treated as chronological chat logs. Do not record the history of changes (e.g., "We first decided X, then changed to Y").
3. **Mandatory Overwrite (Anti-Append-Only)**: When the user points out a mistake, changes their mind, or introduces a new decision that contradicts an older entry in a file, you **MUST NOT** append the correction at the bottom of the file as an erratum. You **MUST** use the `replace_file_content` tool to locate the outdated or incorrect text and overwrite it or delete it entirely. Ensure the file reads as a clean, unified document without self-contradictions.

---
## 1. Role and Positioning of Specs vs Deliverables

Writing documents involves two distinct levels:
* **Specs (Concept & Guidelines)**: Define what *must* be covered (atomic rules, constraints, definitions). Located in `openspec/specs/`. Focuses on **rigor and logic**.
* **Docs (Prose & Polish)**: The actual deliverable documents. Located in `docs/`. Focuses on **readability, flow, tone, and proofreading**.

### Phase Division of Labor:
- **Propose Phase (Specs)**: The Agent ensures the concept and guidelines are clearly documented in `specs/`. Copywriting and phrasing are secondary here.
- **Apply Phase (Docs)**: The Agent reads the specs as boundaries and writes smooth, polished prose into `docs/` (or promotions from `working-draft.md`), focusing on copywriting and readability.

---

## 2. Spec Naming Conventions

All specs are stored at `openspec/specs/{spec-name}/spec.md`.

- Use kebab-case (lowercase with hyphens): `system-requirements`
- Names should describe **capabilities or topics**, not the action of the change.
  - ✅ `safety-requirements` (describes topic)
  - ❌ `doc-update-safety` (describes action)

<!-- TODO: Add prefix naming rules according to your project needs -->

---

## 3. Task Planning and Granularity

### 3.1 Task Granularity Principle
Each task in `tasks.md` should satisfy the principle: **One Task = One Reviewable Design Decision**.
- **Self-Test**: Can this section of changes be presented to another person to ask "Is this design reasonable?" on its own?
  - **YES** → Correct task granularity.
  - **NO (Too small)** → Merge with adjacent tasks.
  - **NO (Too large)** → Split into multiple design decisions.

| Granularity | Example | Issues |
|---|---|---|
| Too Coarse | "Complete state machine documentation" | High review cognitive load, hard to track progress. |
| Too Fine | "Modify 3rd line of section 2.3.1" | Process overhead exceeds actual work value. |
| Just Right | "Define double-unlock logic for FAULT exit" | Individually describable and reviewable. |

- **Definition of Completion**: The design decision must be fully documented, any pending items marked in `TBD-XX` format, with no loose "under discussion" text remaining.

### 3.2 Task Structure for Document-First Changes
When the primary deliverable of a change is engineering documentation (not source code), and `working-draft.md` exists, the `tasks.md` file must adhere to the following structure:

| Sequence | Task Type | Rules / Requirements |
|---|---|---|
| Task 1 (Must be first) | Move draft to final path | `mv working-draft.md <final_destination_path>` — Move only, absolutely no content modifications allowed in Task 1. |
| Task 2 to N | Content editing on the final path | Structure review, logical validation, readability review, and supplementary files. All editing tasks operate directly on the final path. |

**Prohibited Task Structures:**
- ❌ No "copy to final path" or "publish" tasks should exist outside Task 1 — the draft movement must happen exactly once.
- ❌ Do not split logical review and readability review into separate passes — combine them into a single comprehensive read-through.

**Review Consolidation Principle:** Structural logic (argument completeness, terminology alignment) and readability (transitions, phrasing consistency) must be performed in a single pass. Splitting them increases task overhead without improving document quality.

**Applicability:** Automatically active whenever `working-draft.md` exists in the change directory.

---

## 4. Archive Checklist

Follow these steps to process specs during every change archive.

### □ Step 0: Process explore-notes.md

If there is cross-change content (subsequent drafts, roadmaps) → extract and merge it into `openspec/engineering-roadmap.md`.

### □ Step 1: Filter and Categorize

| Type | Add to specs? |
|---|---|
| Core requirements, definitions, rules | ✅ Yes |
| One-time execution tasks | ❌ No |
| Formatting/Layout adjustments | ❌ No |

### □ Step 2: Update or Create Spec

Prioritize updating existing specs. When creating a new spec, confirm: Is it an independent capability and does it have enough content?

### □ Step 3: Completeness Check

- Is the Purpose section still accurate?
- Do the new requirements conflict or overlap with existing specs?
