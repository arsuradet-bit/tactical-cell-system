-- Additive only. Original and previous migration tables remain untouched.
CREATE TABLE IF NOT EXISTS intel_gmon_uploads (
    id BIGSERIAL PRIMARY KEY,
    raw JSONB NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS intel_checkpoints (
    id BIGSERIAL PRIMARY KEY,
    checkpoint_code TEXT NOT NULL,
    checkpoint_name TEXT NOT NULL,
    direction TEXT,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    source_line INTEGER,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (checkpoint_code, lat, lon)
);
-- Repeated survey rows are intentionally preserved.
