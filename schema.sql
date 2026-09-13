-- Run once in Cloud SQL Studio. New tables only; gmon_survey_logs is untouched.
BEGIN;
CREATE TABLE IF NOT EXISTS intel_gmon_observations (
    id BIGSERIAL PRIMARY KEY,
    fingerprint TEXT NOT NULL UNIQUE,
    plmn TEXT NOT NULL,
    xci TEXT NOT NULL,
    lac TEXT NOT NULL,
    xnbid TEXT NOT NULL DEFAULT '',
    local_cid TEXT NOT NULL DEFAULT '',
    system TEXT NOT NULL DEFAULT '',
    lat DOUBLE PRECISION NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lon DOUBLE PRECISION NOT NULL CHECK (lon BETWEEN -180 AND 180),
    observed_at TIMESTAMP NOT NULL,
    rsrp DOUBLE PRECISION,
    rssi DOUBLE PRECISION,
    gps_accuracy DOUBLE PRECISION,
    site_name TEXT NOT NULL DEFAULT '',
    raw JSONB NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS intel_gmon_latest (
    plmn TEXT NOT NULL,
    xci TEXT NOT NULL,
    lac TEXT NOT NULL,
    observation_id BIGINT NOT NULL REFERENCES intel_gmon_observations(id),
    xnbid TEXT NOT NULL DEFAULT '',
    observed_at TIMESTAMP NOT NULL,
    PRIMARY KEY (plmn, xci, lac)
);
CREATE INDEX IF NOT EXISTS intel_latest_cell_lac ON intel_gmon_latest (xci, lac);
CREATE INDEX IF NOT EXISTS intel_latest_lac ON intel_gmon_latest (lac);
CREATE INDEX IF NOT EXISTS intel_latest_nbid ON intel_gmon_latest (xnbid);
CREATE INDEX IF NOT EXISTS intel_observation_history ON intel_gmon_observations (plmn, xci, lac, observed_at DESC);
COMMIT;
