# Status: Milestone 2 (Tagging core)

Date: 2026-10-13. Branch `claude/keen-hawking-km90vd`. Companion to `plan-m2.md`.

## What works

- **Templates**: per-squad code windows with buttons (code, label, hotkey, colour, instant
  with lead/lag or start/stop) and descriptor groups (options or players). Editor with add,
  reorder, recolour, hotkey entry, clash and reserved-key detection as you type, outcome group
  and success values. Saving creates a new version; old versions stay and tags keep theirs.
  Rugby union 15s and sevens defaults for every new squad.
- **Tagging workspace**: player, code window and timeline on one screen. Hotkeys create tags
  at the frame-snapped playhead converted to the event timeline through the video offset;
  instant codes apply lead/lag; start/stop codes open on the first press (pulsing, growing on
  the timeline) and close on the second. Descriptor chips and Shift+letter apply to the
  selected or latest tag; players are picked by shirt number with type-ahead; notes save on
  blur. Every change saves immediately with a version; a conflict shows a plain message and
  adopts the other person's version.
- **Timeline**: canvas, one row per code, zoom (buttons or Ctrl+scroll), scroll, playhead
  synced both ways, click to select and seek, drag bodies and edges with frame snapping,
  marquee and Shift+click multi-select, split at playhead, merge, delete, undo and redo for
  everything (Cmd/Ctrl+Z, Shift+Cmd/Ctrl+Z, Ctrl+Y).
- **Find clips**: chips for codes and descriptor values, players, match, season, opponent,
  type; AND across fields, OR within a field; runs server-side on JSONB containment with the
  GIN index; results with thumbnails; watch in place; saved searches (private or shared).
- **Playlists**: from a search (snapshot, refreshable), hand-picked tags, ad-hoc ranges;
  continuous playback across matches with next/previous and N/P keys; drag reorder; notes;
  rename, duplicate, delete; share with chosen staff, enforced in the API.
- **Stats**: per match or season; counts per code, success rates from the outcome group,
  per-player table; every number opens as a playlist; CSV for both tables.
- **Exports**: clip, playlist or range rendered by `worker-cpu` from the originals (proxy
  fallback), normalised to one size and frame rate, optional captions (code, note, match),
  progress in the UI, listed under Downloads with download and delete.

## How it was verified

| Gate | Result |
| --- | --- |
| `make check` | clean (ruff, mypy strict, eslint, tsc) |
| Backend tests | 45 pytest: templates (validation, versioning, permissions), tags (concurrency conflict, split, merge, batch, 1,500 tags listed in well under 2 s), clip search (AND/OR, descriptors, players, scope, saved filters), playlists (filter, refresh, order, notes, sharing), stats (rates, players, CSV), exports (clip, playlist, range, access, delete), plus Milestone 1 |
| Frontend unit tests | 54 vitest: frame maths, time conversions (offset, 29.97 fps round trips), lead/lag and start/stop logic, descriptor toggling, hotkeys, tag store commands with undo/redo and conflict handling, 1,500 tags in the store |
| Playwright | Milestone 1 smoke test; Milestone 2 scenario: hotkeys (start/stop, instant with lead/lag), Shift+letter descriptor, chip, player picker, timeline drag with frame snapping, undo/redo, split, marquee select and merge, note, Find clips chips and saved search, playlist from a search, play through with next/previous, rename, export to MP4 (file downloaded and checked), stats number opening a playlist; a coach sees only the simple screens |
| Guides | `docs/guides/tagging-a-match.md` and `finding-clips.md`, screenshots captured with Playwright at laptop (1280) and tablet (1024 landscape, 820 portrait) widths |

## Known limits

- Playwright's bundled Chromium cannot decode H.264, so in that browser the scenario drives
  the player through its time model rather than real decoding; CI runs with Google Chrome.
  Safari was not available here: the coach screens use only standard HTML, CSS grid and the
  video element, but please click through them on a Mac during the review.
- Shift+click on the timeline works in real browsers; headless Chromium drops the modifier on
  pointer events, so the scenario multi-selects with a marquee drag instead.
- Undo history is per browser tab and is lost on reload. There is no server-side history
  beyond `updated_by` and `updated_at`.
- A start/stop tag left open when leaving the page is closed at the current playhead.
- Export captions need a font in the worker image (`fonts-dejavu-core` is installed); without
  one the export still succeeds, without captions.
- Playlists and templates use last-write-wins; only tags carry a version.
- Stats use the squad's active template to define success; a template without an outcome
  group gives counts only.

## Spec changes to consider

1. State that tag times are integer milliseconds on the event timeline (ADR 0006) and that
   the player's keys (Space, J, K, L, F, M, comma, full stop) are reserved from templates.
2. Define descriptor hotkeys as Shift+letter so the spec's "hotkeys" cover both buttons and
   descriptors without clashing.
3. Decide who may see a playlist by default: this build shows a playlist to its owner, the
   people it is shared with and squad admins. If every coach should see every playlist in
   the squad, that is a one-line change.
4. "Reorder by drag" needs a pointer; on a tablet the drag handle works but a move up/down
   button would help accessibility. Worth a line in the spec.
5. Exports normalise all clips to one size and frame rate so they concatenate; say so, and
   decide whether 4K originals should export at 4K (currently 1080p).
