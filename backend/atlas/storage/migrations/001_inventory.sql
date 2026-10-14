CREATE TABLE scans (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    mode TEXT NOT NULL,
    error TEXT
);

CREATE TABLE facts (
    id INTEGER PRIMARY KEY,
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    value TEXT NOT NULL,
    certainty TEXT NOT NULL,
    rule TEXT,
    collected_at TEXT NOT NULL
);

CREATE INDEX facts_scan_subject ON facts (scan_id, subject);

CREATE TABLE evidence (
    id INTEGER PRIMARY KEY,
    fact_id INTEGER NOT NULL REFERENCES facts(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    ref TEXT NOT NULL,
    excerpt TEXT NOT NULL,
    file_sha256 TEXT,
    collected_at TEXT NOT NULL
);

CREATE TABLE entities (
    id INTEGER PRIMARY KEY,
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    payload TEXT NOT NULL,
    UNIQUE (scan_id, kind, entity_key)
);

CREATE TABLE sources (
    id INTEGER PRIMARY KEY,
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    collector TEXT NOT NULL,
    target TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT
);

CREATE TABLE changes (
    id INTEGER PRIMARY KEY,
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    previous_scan_id INTEGER,
    entity_kind TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    change_kind TEXT NOT NULL,
    before_json TEXT,
    after_json TEXT
);
