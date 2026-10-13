# 0003. Resumable uploads: tus server inside the API

Status: accepted. Date: 2026-10-13.

## Context

Match files are multi-GB and campus Wi-Fi drops. The spec asks for the tus
resumable upload protocol and leaves the server choice open: `tusd` (Go) or a
Python implementation.

## Decision

The API implements tus 1.0.0 itself (creation, HEAD, PATCH, termination,
expiration) under `/api/uploads`. The browser uses `tus-js-client`.

Reasons:

- Uploads use the same session cookie, CSRF check and squad permissions as
  everything else. With `tusd` that needs HTTP hooks to the API and a second
  trust boundary.
- One fewer container, and the whole path (upload, completion, job enqueue) is
  testable with pytest.
- Throughput is bounded by disk and network, not by Python: PATCH bodies are
  streamed to disk in chunks.

Completion creates the `videos` row, moves the file (same filesystem, atomic
rename) to `originals/<video id>/`, and enqueues a transcode job.

## Consequences

Caddy must not buffer or limit request bodies on `/api/uploads`. If upload
throughput becomes a problem on the server, `tusd` can replace the endpoint
without changing the client, because the protocol is the same.
