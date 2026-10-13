# 0007. Optimistic concurrency with a version column

Status: accepted. Date: 2026-10-13.

## Context

Two staff may edit the same match (an analyst tagging, a coach fixing a boundary). Every
change is saved immediately, so a stale screen must not silently overwrite a newer edit.

## Decision

- `tags.version` starts at 1 and increases by one on every successful update.
- `PATCH`, `DELETE`, split and merge require the version the client last saw. The update is
  `UPDATE tags SET ... , version = version + 1 WHERE id = :id AND version = :version`.
  Zero rows affected means someone else changed the tag: the API answers `409 Conflict` with
  the current tag in the body.
- The client shows "This tag was changed by someone else", replaces its copy with the current
  one, and drops the failed command from the undo stack.
- No locks and no server-side merge: tag edits are small and conflicts are rare, so a clear
  message beats a merge nobody can predict.

## Consequences

Clients must send `version` with every change and refresh on 409. Playlists and templates
use last-write-wins for now; templates are append-only versions anyway.
