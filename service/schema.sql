CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    repo_full_name TEXT NOT NULL,
    pr_number INTEGER NOT NULL,
    head_sha TEXT NOT NULL,
    base_sha TEXT NOT NULL,
    issue_count INTEGER NOT NULL DEFAULT 0,
    verified_patch_count INTEGER NOT NULL DEFAULT 0,
    fix_pr_url TEXT,
    summary TEXT,
    cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    trace_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Kept alongside the columns above so upgrading an existing database (where
-- CREATE TABLE IF NOT EXISTS above is a no-op) still gets the new columns.
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS trace_url TEXT;

CREATE TABLE IF NOT EXISTS review_issues (
    id SERIAL PRIMARY KEY,
    review_id INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    fingerprint TEXT NOT NULL,
    file TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    confidence REAL NOT NULL,
    fixable BOOLEAN NOT NULL,
    dismissed BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_reviews_repo ON reviews (repo_full_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_review_issues_review ON review_issues (review_id);
