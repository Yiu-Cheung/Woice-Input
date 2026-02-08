# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a speech-to-text application managed using **OpenSpec**, a specification-driven development framework. All changes follow a structured workflow from proposal through implementation.

## OpenSpec Workflow

This project uses the **spec-driven schema** with the following artifact sequence:

```
proposal → specs → design → tasks → implementation
```

### Change Lifecycle

1. **Explore** (`/opsx:explore`): Think through problems and clarify requirements before creating a change
2. **New Change** (`/opsx:new <name>`): Create a new change and step through artifacts one-by-one
3. **Fast-Forward** (`/opsx:ff <name>`): Create all artifacts in one go to quickly reach implementation
4. **Continue** (`/opsx:continue [name]`): Create the next artifact for an existing change
5. **Apply** (`/opsx:apply [name]`): Implement the tasks defined in the change
6. **Archive** (`/opsx:archive [name]`): Archive a completed change

### Key Commands

```bash
# List all changes
openspec list --json

# Check change status
openspec status --change "<name>" --json

# Get artifact instructions
openspec instructions <artifact-id> --change "<name>" --json

# Get implementation instructions
openspec instructions apply --change "<name>" --json

# Sync delta specs to main specs
openspec sync --change "<name>"
```

## Directory Structure

```
openspec/
├── config.yaml              # Project configuration
├── changes/                 # Active changes
│   ├── <change-name>/      # Individual change directory
│   │   ├── proposal.md     # Why this change and what capabilities it adds
│   │   ├── specs/          # Delta specs for new/modified capabilities
│   │   ├── design.md       # Technical decisions and architecture
│   │   └── tasks.md        # Implementation checklist
│   └── archive/            # Completed changes (YYYY-MM-DD-<name>)
└── specs/                   # Main capability specifications
    └── <capability>/
        └── spec.md
```

## Artifact Guidelines

### Proposal (proposal.md)
- **Purpose**: Define why the change is needed and what capabilities it adds
- **Capabilities section**: Each capability listed requires a corresponding spec file
- Structure: Why, What Changes, Capabilities, Impact

### Specs (specs/<capability>/spec.md)
- **Purpose**: Define requirements for each capability
- **One spec per capability** listed in the proposal
- Use the **capability name** for the directory, not the change name
- Delta specs live in the change directory during development
- Sync to main specs after implementation using `/opsx:sync`

### Design (design.md)
- **Purpose**: Document technical decisions, architecture, and implementation approach
- Read proposal and specs before creating
- Focus on "how" not "what"

### Tasks (tasks.md)
- **Purpose**: Break down implementation into actionable checkboxes
- Format: `- [ ] Task description`
- Mark complete during implementation: `- [x] Task description`

## Important Constraints

### Context and Rules
When creating artifacts using `openspec instructions`:
- `context` and `rules` fields are **constraints for Claude**, not content for the file
- **DO NOT** copy `<context>`, `<rules>`, or `<project_context>` blocks into artifacts
- Use them to guide what you write, but they should never appear in output files

### Fluid Workflow
- Changes are not phase-locked; you can update artifacts during implementation
- If implementation reveals design issues, update the design artifact
- If new requirements emerge, update specs
- Use `/opsx:continue` to create additional artifacts or update existing ones

### Explore Mode
- `/opsx:explore` is for **thinking, not implementing**
- You may read files and investigate the codebase
- You may create OpenSpec artifacts (proposals, designs, specs)
- **NEVER write application code** in explore mode
- To implement, exit explore mode and use `/opsx:new` or `/opsx:ff`

## Change Selection

When a skill requires a change name but none is provided:
1. Infer from conversation context if a change was mentioned
2. Auto-select if only one active change exists
3. Otherwise, use `openspec list --json` and prompt user with **AskUserQuestion**
   - Show top 3-4 most recently modified changes
   - Mark most recent as "(Recommended)"
   - **DO NOT** guess or auto-select without user confirmation

## Schema Awareness

The default schema is **spec-driven**. To use a different schema:
- User must explicitly request it by name: `--schema <name>`
- Or user asks to see available schemas: `openspec schemas --json`
- **Never assume or suggest** non-default schemas unless user mentions them

Always check `schemaName` from `openspec status --json` to understand which workflow is active, as different schemas have different artifact sequences and requirements.

## Python venv
Always create a virtual environment before running any Python commands.