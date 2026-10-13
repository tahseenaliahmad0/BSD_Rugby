# Rugby Video Analysis Platform: Design Spec

Source of truth for the product. Copied from the original design document; change it by agreement and record the reason in an ADR.

## Overview

We are building a self-hosted replacement for Hudl that lets rugby staff tag match and training footage quickly, with AI that proposes tags for a human to confirm. It runs on the college's Linux GPU server and is used through a web browser on campus.

**Goals**

- Tagging is faster than in Hudl for an analyst, and simple enough for a non-technical coach to filter clips and build playlists without training.
- All footage and data stay on college hardware.
- AI assistance cuts manual tagging time, starting with splitting footage into plays and flagging set pieces.
- Existing Hudl tag history can be imported so past seasons stay searchable.

**Non-goals for now**

- Fully automatic tagging. AI output is always a suggestion until a person accepts it.
- Public internet access. The app is reachable on the campus network only.
- Native desktop or mobile apps. Everything runs in a browser.

**Constraints**

- Footage comes from cameras at varying angles and weather, and the camera often pans and zooms to follow play. Models must not assume a fixed, calibrated camera.
- Coaches use Macs, but the app must work in any modern browser (Chrome, Safari, Firefox, Edge) on any OS.
- Several squads (for example men's, women's, and second teams) share one installation with separate data and permissions.
- Live tagging at the sideline must keep working when the network drops.

## Users and core workflows

Three roles use the app, and the interface for coaches must work with no training: big buttons, plain words, no technical settings.

| Role | What they do | What they need from the UI |
| --- | --- | --- |
| Admin / analyst | Uploads footage, runs AI, tags in detail, manages squads, tag templates and users | Keyboard-driven code window, timeline editing, bulk accept/reject of AI suggestions |
| Coach | Live-tags at the sideline, filters clips, builds and shares playlists, draws on clips, reads stats | A simple filter panel ("all lost lineouts in their 22"), one-click playlists, drawing tools |
| Player (later phase) | Watches playlists shared with them and their own clips | A read-only view with a "My clips" page |

**Match-day workflow**

1. A coach tags key moments live on a laptop at the sideline. Tags are saved locally and synced when the laptop is back on the network.
2. After the match, the analyst uploads the footage. The server transcodes it and starts the AI pipeline in the background.
3. The live tags are aligned to the uploaded video (see Live sideline tagging).
4. The AI adds suggested tags: play segments, stoppages, set pieces. They appear on the timeline as "suggested" until reviewed.
5. The analyst reviews suggestions with keyboard shortcuts (accept, reject, nudge start/end) and adds detail such as players and outcomes.
6. Coaches filter tags into playlists, add drawings and notes, and share them with other staff or players.
7. Every accepted, rejected or corrected suggestion is stored as training data for the next model version.

**Training workflow** is the same minus live tagging, usually with lighter tagging (drills, reps, individual feedback).

## Feature requirements

V1 is a complete manual Hudl replacement plus live tagging and Hudl import; AI assistance arrives in V2 once real tagged data exists to tune it.

| Area | Feature | Phase |
| --- | --- | --- |
| Library | Squads, seasons, matches/sessions, opponents; search by date, opponent, competition | V1 |
| Ingest | Upload by browser (resumable, multi-GB) and from a watched server folder; automatic transcode to a browser-friendly proxy plus thumbnails | V1 |
| Playback | Frame-accurate seek, frame step, 0.25x to 2x speed, J/K/L and arrow-key shortcuts, fullscreen | V1 |
| Tagging | Code window: configurable button grid with hotkeys, lead/lag times, per-squad templates | V1 |
| Tagging | Descriptors on each tag: players, team, field zone, phase count, outcome, free-text note | V1 |
| Tagging | Timeline view: drag to adjust start/end, split, merge, delete, undo | V1 |
| Tagging | Live sideline tagging that works offline and syncs later | V1 |
| Analysis | Filter builder ("tag is Lineout AND outcome is Lost AND zone is Opp 22") and saved filters | V1 |
| Analysis | Playlists: from a filter or hand-picked, reorder, add notes per clip, continuous playback | V1 |
| Analysis | Basic stats from tags: counts, success rates, per-player tables, CSV export | V1 |
| Sharing | Share a playlist with staff; export a playlist or clip as MP4 | V1 |
| Migration | Import Hudl / Sportscode tags (XML, CSV) and match them to uploaded footage | V1 |
| Admin | User accounts, roles, per-squad permissions | V1 |
| AI | Auto-split into play segments and stoppages; set-piece suggestions (scrum, lineout, kickoff) | V2 |
| AI | Review queue: accept, reject, adjust suggestions; confidence threshold per tag type | V2 |
| Analysis | Telestration: arrows, circles, spotlight, freeze-frame with drawings | V2 |
| Sharing | Player accounts and "My clips" page | V2 |
| AI | Player detection and tracking, team assignment by kit colour, "who is in this clip" suggestions | V3 |
| AI | Pitch registration for field-zone suggestions and heatmaps (where pitch lines are visible) | V3 |
| AI | Event spotting (tackle, carry, kick, try) trained on the club's own accepted tags | V3 |
| Playback | Multi-angle sync on one timeline | Later |
| Analysis | Stats dashboards with trends across a season | Later |

**Default rugby union tag template** (editable per squad): kickoff/restart, scrum, lineout, maul, ruck/breakdown, carry, line break, tackle (made / missed / dominant), turnover (won / conceded), kick (box / grubber / touch / contestable / goal), penalty (with infringement), try, conversion, possession start/end. A sevens template ships alongside it.

## Assisted video analysis

The AI never writes tags directly: it writes suggestions with a confidence score, and a person accepts, rejects or adjusts them. Start with play segmentation and set-piece detection, which work on whole frames and so tolerate a moving, zooming camera far better than player tracking does.

**Pipeline, run as background jobs after upload**

1. **Preprocess.** Detect hard cuts and camera restarts (for example with PySceneDetect), estimate global camera motion from optical flow, and sample frames at a fixed rate for the models. Camera motion is subtracted before any "how much are players moving" signal is computed, so a pan is not mistaken for play.
2. **Play segmentation (V2).** Split the video into ball-in-play and stoppage segments using motion energy after camera compensation, crowding of players, and referee whistle detection on the audio track. Output: segment suggestions with start, end and confidence.
3. **Scene and set-piece classification (V2).** Classify sampled frames into scrum, lineout, ruck, maul, kickoff, open play and stoppage, then smooth over time into segments. Published work on rugby broadcasts shows this frame-level approach is viable ([Nonaka et al., CVPR Workshops 2024](https://openaccess.thecvf.com/content/CVPR2024W/CVsports/html/Nonaka_Rugby_Scene_Classification_Enhanced_by_Vision_Language_Model_CVPRW_2024_paper.html)).
   - **Cold start:** before the club has its own training data, a local open-weight vision-language model such as [Qwen3-VL](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct) (Apache 2.0) labels sampled frames zero-shot. It is slow but needs no training.
   - **Steady state:** a small, fast image classifier is fine-tuned on accepted tags plus imported Hudl history, then replaces the VLM for routine runs.
4. **Player detection and tracking (V3).** Detect people with an Apache-2.0 detector such as [RF-DETR](https://github.com/roboflow/rf-detr), track them across frames with a ByteTrack-style tracker, and split teams by clustering kit colours. Jersey numbers are read only when clearly visible and offered as a suggestion. Expect identity swaps in rucks, mauls and scrums; tracks are reset at every cut.
5. **Pitch registration (V3).** On frames where enough pitch lines are visible, estimate a homography to a rugby pitch model (try line, 22, 10 m, halfway, 5 m and 15 m dashes) using methods adapted from soccer field registration such as [PnLCalib](https://www.arxiv.org/abs/2404.08401). Where registration fails, the field zone stays "unknown" rather than guessed.
6. **Event spotting (V3).** Train a temporal action-spotting model (the family led by T-DEED on the SoccerNet benchmark, see [this 2025 paper](https://arxiv.org/pdf/2504.12021v1)) on the club's accepted tags for tackle, carry, kick and try timestamps.

**Handling varied angles, weather and a moving camera**

- Every stage outputs a per-segment confidence; low-confidence output is shown greyed out or hidden, never forced on the reviewer.
- Training uses heavy augmentation (blur, rain streaks, low light, colour shift, crops and zoom) and footage from many grounds.
- Nothing assumes a fixed camera. Pitch registration and tracking are per shot and fail gracefully.
- Each video stores which model versions produced its suggestions, so results can be re-run when a model improves.

**Learning loop**

- Accept, reject and adjust actions are logged against the suggestion that caused them.
- An admin page shows precision and recall per tag type per model version, measured against what reviewers accepted.
- Retraining is a manual, documented command at first, run when enough new reviewed matches exist.

**Licensing note:** Ultralytics YOLO is AGPL-3.0, and Ultralytics says its enterprise licence is required to use YOLO without open-sourcing the whole project, internal tools included ([Ultralytics licensing](https://www.ultralytics.com/license)). RF-DETR's Nano to Large models are Apache 2.0; its XL and 2XL models use a separate PML 1.0 licence. Default to Apache-2.0 or MIT components, and keep the detector behind an interface so it can be swapped.

## Architecture and tech stack

The system is a browser app talking to a Python API on the college server, with background workers for transcoding and AI, all started with one Docker Compose file. A web app means coaches install nothing and it behaves the same on Mac, Windows, Linux or a tablet.

&#91;embedded content: system architecture · 2 clients, 6 server components\]

Both clients reach the server only through Caddy. Transcoding and AI run in workers fed by the Redis queue, so heavy jobs never slow the app down.

| Layer | Choice | Why |
| --- | --- | --- |
| Frontend | React + TypeScript, Vite, Mantine (or shadcn/ui), TanStack Query | Mainstream, well documented, easy to make large, simple controls for coaches |
| Video player | Custom player on the HTML5 video element using `requestVideoFrameCallback` for frame-accurate time | Supported in Chrome and Edge 83+, Firefox 132+, Safari 15.4+ ([web.dev](https://web.dev/articles/requestvideoframecallback-rvfc)) |
| Drawing | Konva (canvas) overlay on the player | Arrows, shapes, freehand, stored as JSON per clip |
| Offline live tagging | Installable PWA with IndexedDB (Dexie) | Keeps working at the sideline with no network, syncs later |
| Uploads | tus resumable upload protocol (Uppy client, tusd or a Python tus server) | Multi-GB match files survive flaky Wi-Fi |
| API | Python 3.12, FastAPI, Pydantic, SQLAlchemy 2, Alembic migrations | Same language as the ML code; typed, auto-generated OpenAPI docs |
| Database | PostgreSQL | Relational tags and filters; JSONB for flexible descriptors |
| Job queue | Celery + Redis, separate `cpu` and `gpu` queues, GPU concurrency of 1 per card | Transcodes and AI runs never block the web app or each other |
| Video processing | FFmpeg (NVENC when available, libx264 otherwise) | Proxies, thumbnails, clip and playlist export |
| ML | PyTorch, OpenCV, PySceneDetect, RF-DETR, a ByteTrack-style tracker, Hugging Face Transformers or vLLM for the VLM | Permissive licences, runs on one NVIDIA GPU |
| Storage | A mounted volume on the server: originals, proxies, thumbnails, exports | Simple to back up; hidden behind a storage interface so MinIO or S3 can be added later |
| Auth | Local accounts, Argon2 password hashes, HTTP-only session cookies; campus LDAP or SSO later if IT allows | No dependency on outside services |
| Web server | Caddy or nginx: HTTPS, serves the built frontend, proxies the API, serves video with HTTP range requests | One entry point; byte-range serving makes seeking fast |
| Deployment | Docker Compose + NVIDIA Container Toolkit | One command to install, upgrade or move to another server |

**Playback format.** Every upload gets an H.264/AAC MP4 proxy with the index at the front (`faststart`) and a keyframe at least every second, so seeking and frame-stepping feel instant in every browser. The original file is kept untouched for re-processing and full-quality export. HLS adaptive streaming is not needed on a campus network and is deferred. Browsers do not guarantee frame-exact seeking on the video element, so a step can occasionally land one frame off; if analysts need exact frames, a WebCodecs-based decoder can be added later ([web.dev](https://web.dev/articles/requestvideoframecallback-rvfc)).

**Repository layout:** `frontend/`, `backend/` (API, workers, importers), `ml/` (models, training scripts, evaluation), `deploy/` (Compose files, Caddy config, backup scripts), `docs/`.

## Data model

Tags are stored against an event's own timeline, not against a video file, and each video carries an offset onto that timeline. That one choice makes live tags, Hudl imports, re-uploads and later multi-angle sync all the same problem: setting an offset.

| Entity | Key fields | Notes |
| --- | --- | --- |
| User | name, email, password hash, active | Global account |
| Squad | name, sport variant (15s, 7s), tag template | Isolation boundary for data and permissions |
| Membership | user, squad, role (admin, analyst, coach, player) | A user can belong to several squads |
| Player | squad, name, shirt number, position, linked user (optional) | Roster per squad and season |
| Season / Opponent | name, dates / name, colours | For filtering and kit-colour hints to the AI |
| Event | squad, type (match, training), date, opponent, venue, kickoff wall-clock time | Owns the timeline everything else hangs on |
| Video | event, camera label, original path, proxy path, fps, duration, offset to event timeline | Several videos per event allowed from day one |
| TagTemplate | squad, buttons (code, hotkey, colour, lead/lag), descriptor groups | The code window; versioned so old tags stay valid |
| Tag | event, code, start, end, descriptors (JSONB), players, note, source (manual, live, import, AI-accepted), created by | The core record coaches filter |
| Suggestion | video, model version, code, start, end, confidence, status (pending, accepted, rejected, adjusted), resulting tag | Kept forever as training and evaluation data |
| Playlist / PlaylistItem | owner, squad, shared with / tag or custom range, order, note | A clip can be a tag or an ad-hoc time range |
| Drawing | playlist item or tag, timestamp, shapes (JSON) | Telestration layer |
| LiveSession | event, device id, wall-clock start, tags captured, sync state | Offline capture before alignment |
| ImportBatch | source file, format, code mapping, alignment offset, report | Re-runnable and reversible imports |
| Job / ModelVersion | type, status, progress, log, input/output refs / name, task, metrics, file path | Background work and model registry |

Descriptors use JSONB with a GIN index so filters like "zone = Opp 22 AND outcome = Lost" stay fast without a column per label group.

## Hudl / Sportscode migration

The primary import format is the Sportscode XML Edit List, because it carries codes, label groups, notes and times in one file and is Hudl's own interchange format. CSV import covers anything exported as a spreadsheet.

**What the XML contains** ([Hudl manual](https://www.hudl.com/support/manuals/sportscode/code/importing-files/xml-edit-list)):

- A `<file>` root, an optional `<SESSION_INFO><start_time>` wall-clock timestamp, and `<ALL_INSTANCES>` holding one `<instance>` per tag.
- Each instance has `<ID>`, `<start>` and `<end>` in seconds (up to 10 decimal places), `<code>` (the row name), any number of `<label>` elements with optional `<group>` and `<text>`, and an optional `<free_text>` note.
- A `<ROWS>` section gives each code a sort order and a 16-bit RGB colour.
- Hudl notes the file is not strictly valid XML: characters such as `&` may appear unescaped. The parser must be tolerant (pre-escape stray ampersands, or use a recovering parser such as lxml with `recover=True`).

**Import flow**

1. The analyst picks an event, uploads the XML (or CSV) and, if available, the matching video.
2. The app lists every distinct code and label group found and asks the analyst to map each to a code and descriptor in the squad's template, or to create new ones. Mappings are saved per squad so later files import in one click.
3. Alignment: if the video is the same file the tags were made on, the offset is zero. Otherwise the analyst marks one shared moment (usually kickoff) in the video and in the imported list, and the app sets the offset.
4. A dry-run report shows counts per code, unmapped labels and any instances outside the video's duration before anything is written.
5. Imported tags are marked `source = import` and linked to their ImportBatch, so a batch can be undone.

**Export** to the same XML format is cheap to add once import exists, which gives the club an exit route and lets them hand data to other Sportscode users.

Imported tags on footage the club still has are also the first training set for the AI, which is why import ships in V1.

## Live sideline tagging

Live tagging is offline-first: every button press is saved on the device with a wall-clock timestamp, and tags are placed on the video later by lining up one shared moment such as kickoff. Because the app is campus-only, away games will always be tagged offline.

**On the device**

- The tagging screen is an installable web app (PWA). It is installed and opened once on campus, which caches the app, the squad's tag template and the roster.
- The screen is a grid of large buttons with optional quick descriptors (for example, tap Lineout, then Won or Lost). Undo-last is always one tap away.
- Period buttons (Kickoff 1st half, Half time, Kickoff 2nd half, Full time) are mandatory anchors for alignment.
- Every press is written to IndexedDB immediately with the device time in milliseconds and a client-generated UUID. A "save backup file" button exports the session as JSON in case the device cannot reach campus for a while.
- Each button has a configurable lead time, because live presses usually come just after the action.

**Syncing and alignment**

1. Back on the campus network, the app uploads the session. Upload is idempotent by UUID, so retries never duplicate tags.
2. The device records its clock offset from the server at every successful contact, so device clock error can be corrected.
3. When the match video is uploaded, the analyst marks kickoff of each half in the video. The app computes one offset per half (cameras are often stopped at half time) and places the live tags.
4. The analyst can nudge the whole session or a single half if it looks off, with a live preview.

If the camera and tagging device are both running at a home game, the same flow applies; no live streaming to the server is needed for V1.

## Deployment and operations

The whole system installs with `docker compose up -d` on the college's Linux GPU server and is reached at a campus hostname over HTTPS. HTTPS is required, not optional: browsers only allow the offline tagging app (service workers) on secure origins.

**Compose services:** `caddy` (HTTPS, static frontend, video range requests), `api`, `worker-cpu` (transcode, import, export), `worker-gpu` (AI jobs, one at a time per GPU), `postgres`, `redis`, and the upload server if tusd is used.

**To confirm with college IT before deployment**

- [ ] Linux distribution, NVIDIA driver version, GPU model and memory
- [ ] Permission to run Docker (or Podman) with the NVIDIA Container Toolkit
- [ ] Storage volume size, and whether it is backed up by IT
- [ ] A campus hostname and a TLS certificate that college laptops trust
- [ ] Firewall rule limiting access to the campus network
- [ ] College policy on storing video and personal data of student athletes

**Operations**

- Database: nightly `pg_dump` to a separate disk, with a documented, tested restore.
- Video: originals are the irreplaceable asset; back them up under IT's storage policy. Proxies and thumbnails can be regenerated.
- Disk: an admin page shows storage used per squad and season, and warns before the volume fills. Footage size depends on camera bitrate, so measure the first few matches and project from there.
- Upgrades: pull the new version and restart Compose; database migrations run automatically on API start.
- Health: a `/health` endpoint, a jobs page showing queued, running and failed jobs with logs, and structured logs to files.

**Development:** the same Compose file runs on a developer's Mac or Windows laptop without a GPU. AI jobs fall back to CPU or are disabled by a setting, and a small sample-video fixture lets the app be developed without real match footage.

## Roadmap and milestones

Six milestones in three releases, with V1 a complete Hudl replacement before any AI work starts. No dates are set yet; each milestone ends with a short review with coaches before the next begins.

&#91;embedded content: roadmap · 6 milestones, 3 releases, 2 gates\]

The V1 gate is the one that matters: AI work only starts once coaches are using the manual app for real, which also produces the reviewed tags the models train on.

In text form, for Markdown exports: M0 Foundations, M1 Footage and playback, M2 Tagging core, M3 Live tagging and Hudl import (V1 gate), M4 AI assist (V2 gate), M5 Deeper AI.

## Risks and open questions

The biggest risk is not technical: if coaches find the app harder than Hudl, they will not switch, however good the AI is.

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Coaches find the UI confusing | App is abandoned | Separate simple coach views from the analyst workspace; test each milestone with two coaches before moving on |
| Moving camera, angles and weather hurt AI accuracy | Suggestions are ignored | Start with whole-frame tasks; measure on the club's own footage before promising anything; confidence thresholds per tag type |
| Too little labelled data | Models stay weak | Hudl import as training data; VLM cold start; every review action logged |
| Server limits (no Docker, shared GPU, small disk) | Delays or redesign | Confirm the IT checklist first; keep everything portable and CPU-capable for development |
| Live tags misaligned with video | Live tagging distrusted | Per-half anchors, nudge with preview, clock-offset logging |
| Maintainer leaves (for example, graduates) | App rots | Mainstream stack, tests, an admin guide in plain language, one-command deploy |
| Model licences | Legal exposure for the college | Apache-2.0 / MIT components only by default; licences listed in `docs/licenses.md` |

**Open questions**

- [ ] Which Hudl products does the club use (Hudl web, Sportscode, Assist), and can they export XML or CSV plus the original video for past seasons?
- [ ] Camera details: model, resolution, frame rate and file format, and how files get from camera to server.
- [ ] Which five tag types matter most to the coaches? That decides which AI suggestions to build first.



## Sources

- [Hudl Sportscode manual: XML Edit List](https://www.hudl.com/support/manuals/sportscode/code/importing-files/xml-edit-list)
- [web.dev: requestVideoFrameCallback](https://web.dev/articles/requestvideoframecallback-rvfc)
- [RF-DETR repository and licence](https://github.com/roboflow/rf-detr)
- [Ultralytics licensing](https://www.ultralytics.com/license)
- [Qwen3-VL-8B-Instruct model card](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)
- [Nonaka et al., Rugby Scene Classification Enhanced by Vision Language Model, CVPR Workshops 2024](https://openaccess.thecvf.com/content/CVPR2024W/CVsports/html/Nonaka_Rugby_Scene_Classification_Enhanced_by_Vision_Language_Model_CVPRW_2024_paper.html)
- [Gutierrez-Perez and Agudo, PnLCalib: Sports Field Registration via Points and Lines Optimization](https://www.arxiv.org/abs/2404.08401)
- [Action Anticipation from SoccerNet Football Video Broadcasts (describes T-DEED as the state of the art in action spotting)](https://arxiv.org/abs/2504.12021)
