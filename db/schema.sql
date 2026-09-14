-- Minimal demo-scoped schema, built 2026-09-14 to unblock the presentation
-- artifact -- NOT the full P2D phase (the Q1-Q5 acceptance queries per
-- PROMPTS.md P2D, the general mapping_candidate review workflow beyond
-- this one recorded decision, and the required self-verification loader
-- output are not present; the source/profile/mapping_candidate tables
-- themselves ARE present below -- corrected from the first draft of this
-- note, which claimed otherwise). Full P2D remains open, tracked in every
-- prior gate file's "Not proceeding to P2D" status.
--
-- P2D schema, per PROMPTS.md P2D. Built specifically to back
-- scripts/build_demo.py's Postgres-backed demo query -- NOT the full P2D
-- phase (Q1-Q5 acceptance queries, the full mapping_candidate review-queue
-- workflow, embedding backfill). That remains deferred; see
-- gate/P2E-profiles.md's open-items summary ("P2D -- deferred"), which this
-- file does not retroactively close. Scoped down to what the demo needs:
-- the `value`/`doc_item`/`artifact`/`source`/`profile`/`mapping_candidate`
-- tables exist and are populated with REAL extracted rows (all of Sandip's
-- and IIT Bombay's converted NIRF artifacts, not a cherry-picked subset),
-- with exactly one real, explicitly-recorded kpi_code mapping decision
-- (P02, median salary -- see scripts/build_demo.py's own comment on why
-- P02, not the P03 originally named, and who decided it).
--
-- Idempotent: safe to re-run. CREATE TABLE IF NOT EXISTS everywhere;
-- the value-immutability trigger is dropped and recreated so re-running
-- this file cannot silently leave a stale trigger definition behind.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS source (
    source_id           TEXT PRIMARY KEY,
    country              TEXT NOT NULL,
    institution_code     TEXT NOT NULL,
    pattern               TEXT,
    entry_type            TEXT NOT NULL,
    robots_checked_at     TIMESTAMPTZ,
    terms_reviewed_at     TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS profile (
    profile_id    TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    version         TEXT NOT NULL,
    fingerprint      JSONB NOT NULL,
    blocks            JSONB NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifact (
    sha256          TEXT PRIMARY KEY,
    source_id       TEXT NOT NULL REFERENCES source(source_id),
    url              TEXT NOT NULL,
    run_id            TEXT NOT NULL,
    fetched_at         TIMESTAMPTZ NOT NULL,
    http_status         INTEGER NOT NULL,
    content_type         TEXT,
    n_pages               INTEGER,
    classify_label          TEXT NOT NULL,
    profile_id               TEXT REFERENCES profile(profile_id),
    match_status               TEXT NOT NULL CHECK (match_status IN ('MATCH', 'PARTIAL', 'NONE'))
);

CREATE TABLE IF NOT EXISTS doc_item (
    item_id       TEXT PRIMARY KEY,
    sha256         TEXT NOT NULL REFERENCES artifact(sha256),
    page_no          INTEGER,
    bbox              JSONB,
    item_type          TEXT NOT NULL,
    text                TEXT NOT NULL,
    tsv                  tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    embedding              vector(768)
);

CREATE INDEX IF NOT EXISTS doc_item_tsv_idx ON doc_item USING GIN (tsv);

CREATE TABLE IF NOT EXISTS mapping_candidate (
    candidate_id       BIGSERIAL PRIMARY KEY,
    sha256              TEXT NOT NULL REFERENCES artifact(sha256),
    item_id               TEXT NOT NULL REFERENCES doc_item(item_id),
    label_text             TEXT NOT NULL,
    proposed_kpi_code        TEXT NOT NULL,
    score                     NUMERIC,
    status                     TEXT NOT NULL,
    decided_by                  TEXT,
    decided_at                    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS value (
    value_id          BIGSERIAL PRIMARY KEY,
    kpi_code            TEXT NOT NULL,
    institution_code      TEXT NOT NULL,
    period_value            TEXT NOT NULL,
    period_type               TEXT,
    raw_value                  TEXT NOT NULL,
    normalized_value              NUMERIC,
    sha256                          TEXT NOT NULL REFERENCES artifact(sha256),
    item_id                           TEXT NOT NULL REFERENCES doc_item(item_id),
    profile_id                         TEXT NOT NULL REFERENCES profile(profile_id),
    auth_status                          TEXT NOT NULL CHECK (auth_status IN ('CONFIRMED', 'CONFLICTING', 'UNVERIFIED', 'NOT_APPLICABLE')),
    run_id                                TEXT NOT NULL,
    confidence                             NUMERIC
);

-- Deliberately NO UNIQUE(kpi_code, institution_code, period_value) -- see
-- PROMPTS.md P2D: that constraint would silently enforce the exact
-- overwrite P-5 forbids. Identity is
-- (kpi_code, institution_code, period_value, sha256, run_id), enforced by
-- convention (every load is an INSERT, never an UPDATE), not by a unique
-- index here.

CREATE INDEX IF NOT EXISTS value_kpi_inst_period_idx ON value (kpi_code, institution_code, period_value);

-- Make P-5 structurally impossible on `value`, not merely documented.
CREATE OR REPLACE FUNCTION value_no_update_no_delete() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'value is insert-only (P-5): % on value.value_id=% is forbidden', TG_OP, OLD.value_id;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS value_immutable ON value;
CREATE TRIGGER value_immutable
    BEFORE UPDATE OR DELETE ON value
    FOR EACH ROW EXECUTE FUNCTION value_no_update_no_delete();
