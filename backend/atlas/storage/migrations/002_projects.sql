CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    root_path TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    anchor_kind TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE INDEX projects_scan ON projects (scan_id, project_id);

CREATE TABLE edges (
    id INTEGER PRIMARY KEY,
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    src TEXT NOT NULL,
    dst TEXT NOT NULL,
    kind TEXT NOT NULL,
    evidence_ref TEXT
);

CREATE TABLE docs (
    id INTEGER PRIMARY KEY,
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL,
    path TEXT NOT NULL,
    mtime TEXT,
    size INTEGER NOT NULL,
    sha256 TEXT,
    body TEXT NOT NULL
);

CREATE VIRTUAL TABLE docs_fts USING fts5(
    project_id UNINDEXED,
    scan_id UNINDEXED,
    path,
    body,
    tokenize = 'unicode61'
);
