-- Additive only. Original and previous migration tables remain untouched.
CREATE TABLE IF NOT EXISTS intel_gmon_uploads (
    id BIGSERIAL PRIMARY KEY,
    raw JSONB NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Repeated survey rows are intentionally preserved.
