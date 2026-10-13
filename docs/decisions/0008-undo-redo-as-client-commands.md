# 0008. Undo and redo as a client-side command stack

Status: accepted. Date: 2026-10-13.

## Context

Analysts need undo for every tagging and timeline action (create, move, resize, split,
merge, delete, descriptor change). Changes are saved immediately to the server (ADR 0007).

## Decision

- The tagging workspace keeps a command stack. A command knows how to apply itself and how
  to revert itself, both against the API and the local store; it stores the full previous
  state of each tag it touches (a snapshot), not a diff.
- Undo of a delete re-creates the tag with its original id (the API accepts a client id), so
  playlist items and drawings that referenced it work again. Undo of a merge deletes the
  merged tag and re-creates the originals; undo of a split deletes the new half and restores
  the original.
- The stack is per browser session and only holds that user's own actions. Another user's
  concurrent edit surfaces as a 409 on the next command touching that tag; that command is
  dropped and the tag reloaded.
- Keys: Cmd/Ctrl+Z undo, Shift+Cmd/Ctrl+Z or Ctrl+Y redo. Both also sit on the toolbar.

## Consequences

Each command does one or a few API calls; a merge of n tags is one call. The stack is
bounded (200 entries). Server-side history is not kept yet; `updated_by` and `updated_at`
give the minimum audit trail.
