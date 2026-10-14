CREATE TABLE alert_rules (
    name TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    enabled INTEGER NOT NULL
);

CREATE TABLE alert_channels (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    target TEXT NOT NULL,
    enabled INTEGER NOT NULL
);

CREATE TABLE alert_events (
    id INTEGER PRIMARY KEY,
    rule_name TEXT NOT NULL,
    subject TEXT NOT NULL,
    state TEXT NOT NULL,
    message TEXT NOT NULL,
    ts TEXT NOT NULL,
    delivered INTEGER NOT NULL
);

CREATE TABLE metric_rollups (
    series TEXT NOT NULL,
    step INTEGER NOT NULL,
    ts INTEGER NOT NULL,
    value REAL NOT NULL,
    PRIMARY KEY (series, step, ts)
);
