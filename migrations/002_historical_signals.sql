-- Migration: Add historical_signals table for filter novelty scoring
-- Date: 2026-07-18

CREATE TABLE IF NOT EXISTS historical_signals (
    id VARCHAR(64) PRIMARY KEY,
    batch_id VARCHAR(64) NOT NULL,
    item_id VARCHAR(64) NOT NULL,
    content_fingerprint VARCHAR(64) NOT NULL,
    title TEXT NOT NULL,
    normalized_text TEXT DEFAULT '',
    source_type VARCHAR(32) NOT NULL,
    published_at TIMESTAMP WITH TIME ZONE,
    domain VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_historical_signals_published ON historical_signals(published_at);
CREATE INDEX IF NOT EXISTS idx_historical_signals_domain ON historical_signals(domain);
CREATE INDEX IF NOT EXISTS idx_historical_signals_fingerprint ON historical_signals(content_fingerprint);

-- Note: This table stores accepted/qualified items from filter runs for novelty comparison
-- Old items can be deleted after N days based on retention policy
