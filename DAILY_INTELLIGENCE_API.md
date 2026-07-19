# Daily Intelligence API v2

All review mutations accept `X-Reviewer-Id` and `X-Reviewer-Role` (`reviewer` or `admin`). Replace this integration seam with the deployment identity provider.

- `POST /api/daily-intelligence/run` queues a batch.
- `GET /api/daily-intelligence/batches` and `GET /batches/{id}` return history and progress.
- `GET /api/daily-intelligence/batches/{id}/items` supports source/status/keyword/score filters, sorting, and pagination.
- `GET /api/daily-intelligence/batches/{id}/summaries` returns item, source-type, and batch summaries.
- `PATCH /api/daily-intelligence/summaries/{id}` preserves AI output while saving or restoring edits.
- `POST .../approve`, `POST .../reject`, and `POST /summaries/bulk-review` record decisions.
- `POST /api/daily-intelligence/batches/{id}/submit-review` locks an approved snapshot.
- `GET /api/daily-intelligence/batches/{id}/approved-data` exposes the downstream contract.
- `GET /api/daily-intelligence/batches/{id}/export.pdf` exports approved/edited items; query flags can include pending/rejected.
- `GET /api/daily-intelligence/export-all.pdf` exports all canonical records, batch provenance, and latest source-run coverage stored in PostgreSQL/Neon.
- `GET /api/daily-intelligence/source-health` reports sanitized latest source outcomes.
