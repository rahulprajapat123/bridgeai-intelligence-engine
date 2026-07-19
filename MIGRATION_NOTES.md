# Daily Intelligence v2 migration

The migration is additive. `daily_intelligence_reports` and its legacy JSON fields remain unchanged. The new UI reads `ingestion_batches`, `daily_raw_items`, `daily_source_references`, `summaries`, `daily_source_runs`, and `daily_audit_logs`.

Current deployments use SQLAlchemy `create_all`, so starting the updated service creates all new tables safely. PostgreSQL operators can apply `migrations/001_daily_intelligence_v2.sql` before deployment; application startup completes the remaining additive tables. Back up the database first. No Analyze Brief table is altered.
