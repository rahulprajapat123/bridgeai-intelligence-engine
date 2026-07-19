# Signal Filter API

- `POST /api/signal-filter/runs` creates a synchronous run; `Idempotency-Key` is supported per process.
- `GET /api/signal-filter/runs/{run_id}` reads a run.
- `GET /api/signal-filter/runs/{run_id}/items` supports status filtering and pagination.
- `GET /api/signal-filter/runs/{run_id}/decisions` returns paginated audit decisions.
- `POST /api/signal-filter/runs/{run_id}/review` accepts or rejects a review item.
- `PATCH /api/signal-filter/items/{item_id}` edits generated fields.
- `POST /api/signal-filter/items/{item_id}/regenerate` returns 501 until a server-side provider is configured.
- `GET|PATCH /api/signal-filter/config` reads or updates process configuration.
- `GET /api/signal-filter/metrics` returns aggregate process metrics.

The current API store is process-local and intended for local evaluation. Production must use an authenticated durable repository and distributed idempotency store. Source documents are untrusted data and provider prompts must delimit them and prohibit following embedded instructions.
