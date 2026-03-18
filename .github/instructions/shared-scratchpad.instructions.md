---
name: 'Shared Scratchpad'
description: 'Cross-agent shared scratchpad protocol. Tells agents how to read and update the shared scratchpad that persists context across handoffs.'
applyTo: 'shared-scratchpads/**'
---

# Shared Scratchpad Protocol

This file is a **shared scratchpad** — an append-only log that persists context across agent
handoffs (Planner → Implementer → Reviewer). It was created by the Planner. All agents append to it.

## Rules

1. **APPEND ONLY** — never edit, rewrite, reorder, or delete existing content. Only add new entries
   at the end of the file. If earlier information turns out to be wrong, append a correction — don't
   edit the original.
2. **Timestamp every entry** — use the format `## [Agent] — [Phase] (YYYY-MM-DD HH:MM)`.
3. **Every agent appends before finishing** — no silent handoffs. If you did work, log it.
4. **Keep entries concise** — bullet points, not paragraphs. Reference file paths instead of pasting code.

## What to Log

- Key decisions and their rationale
- Constraints discovered that weren't in the plan
- Approach changes and why
- Blockers or workarounds applied
- Test results that revealed unexpected behavior
- Review findings and verdict (Reviewer)

## What NOT to Log

- **Routine actions** — opened file, ran lint, read docs, "researching codebase"
- **Status narration** — "starting work", "reading epic doc", "research complete"
- **Progress without substance** — if the entry has no decision, finding, or constraint, don't log it
- Full code snippets — reference the file path instead
- Anything already captured in the plan chat output

## Entry Format

```markdown
## [Agent Name] — [Brief Phase] (YYYY-MM-DD HH:MM)
- Decision: ...
- Found: ...
- Changed approach: ...
```

## Completion

When the Reviewer approves with no rework needed, append:

```
## Reviewer — Final Approval (YYYY-MM-DD HH:MM)
- Verdict: ✅ Approve
- ...findings...

════════════════════
  IMPLEMENTATION COMPLETE
════════════════════
```

The file stays in `shared-scratchpads/`. The user decides whether to keep, move, or delete it.

## Resume

If asked to resume previous work, the Planner checks `shared-scratchpads/` for an existing
scratchpad, reads it, and plans from where it left off.
