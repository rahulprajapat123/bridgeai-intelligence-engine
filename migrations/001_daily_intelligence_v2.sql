-- Daily Intelligence v2, PostgreSQL reference migration.
-- Existing daily_intelligence_reports data is preserved and deprecated only in the v2 UI.
-- The application SQLAlchemy metadata is authoritative; deployments without Alembic may
-- apply this migration by running the application once (Base.metadata.create_all).
CREATE TABLE IF NOT EXISTS ingestion_batches (
  id varchar(64) PRIMARY KEY, batch_type varchar(32) NOT NULL DEFAULT 'daily_intelligence',
  started_at timestamptz, completed_at timestamptz, status varchar(32) NOT NULL DEFAULT 'created',
  total_sources integer NOT NULL DEFAULT 0, successful_sources integer NOT NULL DEFAULT 0,
  failed_sources integer NOT NULL DEFAULT 0, total_raw_items integer NOT NULL DEFAULT 0,
  unique_items integer NOT NULL DEFAULT 0, duplicate_items integer NOT NULL DEFAULT 0,
  summarized_items integer NOT NULL DEFAULT 0, approved_items integer NOT NULL DEFAULT 0,
  rejected_items integer NOT NULL DEFAULT 0, edited_items integer NOT NULL DEFAULT 0,
  configuration_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb, error_summary jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_by varchar(120) NOT NULL DEFAULT 'system', review_locked boolean NOT NULL DEFAULT false,
  approved_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
-- Remaining normalized tables are created non-destructively from models.py during init_db.
-- This split is intentional for current installations, which use create_all plus compatibility patches.
