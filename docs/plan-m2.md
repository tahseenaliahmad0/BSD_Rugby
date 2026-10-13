# Plan: Milestone 2 (Tagging core)

Goal: an analyst tags a full match quickly with the keyboard and fixes tags on a timeline; a
coach finds clips, builds a playlist, watches it and exports it. Builds on Milestones 0 and 1
(`plan-m0-m1.md`); the spec is `docs/SPEC.md`.

## Data model changes (migration 0002, reversible)

All times on the event timeline become integer milliseconds (ADR 0006):

| Table | Change |
| --- | --- |
| `videos` | `offset_s` float -> `offset_ms` integer |
| `tags` | `start_s`/`end_s` float -> `start_ms`/`end_ms` integer; add `version` (optimistic concurrency, ADR 0007), `updated_by`; index `(event_id, code)` |
| `tag_templates` | add `family_id` (groups versions), `outcome_group`, `success_values` JSONB, `updated_at`; unique `(family_id, version)` |
| `suggestions` | `start_s`/`end_s` -> `start_ms`/`end_ms` (video-relative) |
| `playlist_items` | `start_s`/`end_s` -> `start_ms`/`end_ms`; add `video_id` (optional, for ad-hoc ranges) |
| `playlists` | add `filter_definition` JSONB (source of a filter-built playlist), `saved_filter_id` |
| `drawings` | `timestamp_s` -> `timestamp_ms` |
| `live_tags` | `lead_s` -> `lead_ms` |
| `import_batches` | `alignment_offset_s` -> `alignment_offset_ms` |
| new `saved_filters` | `squad_id`, `owner_id`, `name`, `definition` JSONB, `is_shared` |
| new `exports` | `squad_id`, `owner_id`, `name`, `kind`, `playlist_id`, `clips` JSONB snapshot, `with_captions`, `status`, `job_id`, `file_path`, `size_bytes`, `error`, timestamps |

Template JSON (validated by Pydantic, stored in JSONB):

```
buttons: [{ code, label, hotkey, colour, kind: "instant" | "span", lead_ms, lag_ms, groups: [group key] }]
descriptor_groups: [{ key, label, kind: "options" | "players", multiple, options: [{ value, label, hotkey? }] }]
outcome_group: "outcome", success_values: ["Won"]
```

Tag descriptors: `{ group key: value | [values] }`; players live in `tag_players` and are
returned as `player_ids`. Codes are stored on the tag by name (`code`), so a tag survives a
template edit; `template_id` records the exact version it was made with.

## API

Templates: `GET/POST /api/squads/{id}/templates`, `POST /api/squads/{id}/templates/defaults`,
`GET /api/templates/{id}`, `PUT /api/templates/{id}` (creates version n+1 and activates it),
`GET /api/templates/{id}/versions`, `DELETE /api/templates/{id}` (deactivate family).

Tags: `GET/POST /api/events/{id}/tags`, `POST /api/events/{id}/tags/batch`,
`PATCH /api/tags/{id}` (requires `version`; 409 with the current tag on mismatch),
`DELETE /api/tags/{id}?version=`, `POST /api/tags/{id}/split`, `POST /api/events/{id}/tags/merge`.
Creates accept a client-supplied `id` so undo can restore a deleted tag under the same id.

Clips: `POST /api/squads/{id}/clips/search` (filter definition -> clips with event, video,
video-relative times and a thumbnail), `GET/POST/PATCH/DELETE` saved filters under
`/api/squads/{id}/filters` and `/api/filters/{id}`.

Playlists: `GET/POST /api/squads/{id}/playlists`, `GET/PATCH/DELETE /api/playlists/{id}`,
`POST .../items`, `PATCH/DELETE .../items/{item_id}`, `PUT .../order`, `POST .../refresh`,
`POST .../duplicate`, `PUT .../shares`.

Stats: `GET /api/squads/{id}/stats?event_id=|season_id=` with `format=csv&table=codes|players`.

Exports: `POST /api/squads/{id}/exports`, `GET /api/squads/{id}/exports`, `GET/DELETE
/api/exports/{id}`; the file is served at `/media/exports/{id}/<name>.mp4` through the same
access check as video.

## Screens

| Route | Who | What |
| --- | --- | --- |
| `/squads/:id/templates`, `/templates/:id` | analyst | template list and editor (buttons, hotkeys with clash detection, colours, descriptor groups, outcome group) |
| `/matches/:id/tag` | analyst | tagging workspace: player, code window, timeline, undo/redo |
| `/squads/:id/clips` | coach, analyst | Find clips: plain-language chips, results with thumbnails, watch, save filter, save as playlist |
| `/squads/:id/playlists`, `/playlists/:id` | coach, analyst | playlists, continuous playback with next/previous, reorder, notes, share, export |
| `/squads/:id/stats` | coach, analyst | counts and success rates per code, per-player table, click a number to open the clips as a playlist, CSV |
| `/squads/:id/downloads` | coach, analyst | finished exports to download or delete |

The coach never sees the timeline or code window unless they open the analyst view
("Tag this match" on the match page, shown only to admins and analysts).

## Order of work

1. Spec into the repo, this plan, ADRs 0006 to 0008.
2. Migration 0002 and model updates; Milestone 1 code moved to milliseconds.
3. Templates: schema validation, versioning, default 15s and sevens templates, API, tests.
4. Tags: API with optimistic concurrency, split, merge, batch; tests including a conflict and a 1,500-tag event.
5. Clip search: filter-to-SQL builder on JSONB with the GIN index, saved filters, tests.
6. Playlists API and tests. 7. Stats and CSV, tests. 8. Export worker and API, tests.
9. Frontend: template editor. 10. Tagging workspace (store with undo/redo, code window, canvas timeline). 11. Find clips, playlists and continuous player, stats, downloads.
12. Playwright scenario, coach guides with screenshots, clean-checkout run, report.

## Spec ambiguities resolved

| Question | Decision |
| --- | --- |
| Where do template hotkeys and player shortcuts collide? | The player keeps Space, J, K, L, F, M, arrows, comma, full stop, Home, End and Cmd/Ctrl+Z/Y. The template editor refuses those keys and flags duplicates. Default templates use digits and the remaining letters. |
| What does "instant" mean for a start/stop code pressed once? | A span code opens on the first press and closes on the second. Leaving the workspace with a span open keeps it open (shown in the timeline); it closes at the video end if the video ends. |
| Which template defines stats when tags point at old versions? | The squad's active template version defines codes, outcome group and success values for stats. Tags keep their own `template_id` for history. |
| Who can see a playlist? | Its owner, the staff it is shared with, and squad admins. Only the owner and squad admins edit it. |
| Where does an ad-hoc playlist range play from? | From the event's first ready video unless the item names a video. |
| Export source | The original file when it still exists, else the proxy; clips are normalised to one size and frame rate so they concatenate. Captions use the DejaVu font shipped in the image; without a font the caption is skipped and logged. |
| Players in filters | Players live in `tag_players` (a join), not in the JSONB, so a renamed player keeps matching. |
