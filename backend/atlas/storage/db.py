"""SQLite storage: snapshots, facts, evidence, and the change log between scans."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from atlas.domain import CollectorResult, Entity, Fact
from atlas.redact import mask_secrets

MIGRATIONS = Path(__file__).resolve().parent / "migrations"


def connect(path: Path) -> sqlite3.Connection:
    """Open the state database, apply migrations, and keep the file private."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    apply_migrations(conn)
    os.chmod(path, 0o600)
    return conn


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply pending SQL migrations in filename order."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.name in applied:
            continue
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (path.name, datetime.now(UTC).isoformat()),
        )


class Store:
    """Read and write one ATLAS database."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @classmethod
    def open(cls, path: Path) -> Store:
        return cls(connect(path))

    def close(self) -> None:
        self._conn.close()

    def start_scan(self, mode: str) -> int:
        """Insert a scan row and return its id. The row stays ``running`` until finish."""
        cursor = self._conn.execute(
            "INSERT INTO scans (started_at, status, mode) VALUES (?, 'running', ?)",
            (datetime.now(UTC).isoformat(), mode),
        )
        self._conn.commit()
        return _row_id(cursor)

    def finish_scan(self, scan_id: int, status: str, error: str | None = None) -> None:
        self._conn.execute(
            "UPDATE scans SET finished_at = ?, status = ?, error = ? WHERE id = ?",
            (datetime.now(UTC).isoformat(), status, error, scan_id),
        )
        self._conn.commit()

    def persist(self, scan_id: int, results: list[CollectorResult]) -> int:
        """Store collector output and the diff against the previous successful scan."""
        self._conn.execute("BEGIN")
        try:
            self._insert_facts(scan_id, results)
            self._insert_entities(scan_id, results)
            self._insert_sources(scan_id, results)
            changes = self._record_changes(scan_id)
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        return changes

    def latest_successful_scan(self) -> int | None:
        row = self._conn.execute(
            "SELECT id FROM scans WHERE status = 'succeeded' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return int(row["id"])

    def entities(self, scan_id: int, kind: str | None = None) -> list[dict[str, Any]]:
        if kind is None:
            rows = self._conn.execute(
                "SELECT kind, entity_key, payload FROM entities WHERE scan_id = ? ORDER BY kind, entity_key",
                (scan_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT kind, entity_key, payload FROM entities "
                "WHERE scan_id = ? AND kind = ? ORDER BY entity_key",
                (scan_id, kind),
            ).fetchall()
        return [_entity_row(row) for row in rows]

    def sources(self, scan_id: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT collector, target, status, reason FROM sources WHERE scan_id = ? ORDER BY collector, target",
            (scan_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def facts(self, scan_id: int, subject: str | None = None) -> list[dict[str, Any]]:
        if subject is None:
            rows = self._conn.execute(
                "SELECT id, subject, predicate, value, certainty, rule, collected_at "
                "FROM facts WHERE scan_id = ? ORDER BY id",
                (scan_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, subject, predicate, value, certainty, rule, collected_at "
                "FROM facts WHERE scan_id = ? AND subject = ? ORDER BY id",
                (scan_id, subject),
            ).fetchall()
        return [dict(row) for row in rows]

    def evidence_for_fact(self, fact_id: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT id, kind, ref, excerpt, file_sha256, collected_at "
            "FROM evidence WHERE fact_id = ? ORDER BY id",
            (fact_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def changes(self, scan_id: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT entity_kind, entity_key, change_kind, before_json, after_json, previous_scan_id "
            "FROM changes WHERE scan_id = ? ORDER BY id",
            (scan_id,),
        ).fetchall()
        decoded: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["before"] = _loads(item.pop("before_json"))
            item["after"] = _loads(item.pop("after_json"))
            decoded.append(item)
        return decoded

    def dump_text(self, scan_id: int) -> str:
        """Serialize everything stored for a scan. Secret tests search this blob."""
        chunks: list[str] = []
        for row in self._conn.execute(
            "SELECT subject, predicate, value, certainty, rule FROM facts WHERE scan_id = ?",
            (scan_id,),
        ):
            chunks.append(" ".join("" if value is None else str(value) for value in row))
        for row in self._conn.execute(
            "SELECT e.kind, e.ref, e.excerpt FROM evidence e "
            "JOIN facts f ON f.id = e.fact_id WHERE f.scan_id = ?",
            (scan_id,),
        ):
            chunks.append(" ".join(str(value) for value in row))
        for row in self._conn.execute(
            "SELECT kind, entity_key, payload FROM entities WHERE scan_id = ?",
            (scan_id,),
        ):
            chunks.append(" ".join(str(value) for value in row))
        return "\n".join(chunks)

    def _insert_facts(self, scan_id: int, results: list[CollectorResult]) -> list[int]:
        ids: list[int] = []
        for result in results:
            for item in result.facts:
                ids.append(self._insert_fact(scan_id, item))
        return ids

    def _insert_fact(self, scan_id: int, item: Fact) -> int:
        cursor = self._conn.execute(
            "INSERT INTO facts (scan_id, subject, predicate, value, certainty, rule, collected_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                scan_id,
                item.subject,
                item.predicate,
                item.value,
                item.certainty.value,
                item.rule,
                item.collected_at.isoformat(),
            ),
        )
        fact_id = _row_id(cursor)
        for proof in item.evidence:
            self._conn.execute(
                "INSERT INTO evidence (fact_id, kind, ref, excerpt, file_sha256, collected_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    fact_id,
                    proof.kind.value,
                    proof.ref,
                    proof.excerpt,
                    proof.file_sha256,
                    proof.collected_at.isoformat(),
                ),
            )
        return fact_id

    def _insert_entities(self, scan_id: int, results: list[CollectorResult]) -> None:
        for result in results:
            for item in result.entities:
                self._insert_entity(scan_id, item)

    def _insert_entity(self, scan_id: int, item: Entity) -> None:
        self._conn.execute(
            "INSERT INTO entities (scan_id, kind, entity_key, payload) VALUES (?, ?, ?, ?)",
            (
                scan_id,
                item.kind,
                item.key,
                json.dumps(_mask_payload(item.payload), sort_keys=True, default=str),
            ),
        )

    def _insert_sources(self, scan_id: int, results: list[CollectorResult]) -> None:
        for result in results:
            for source in result.sources:
                self._conn.execute(
                    "INSERT INTO sources (scan_id, collector, target, status, reason) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (scan_id, source.collector, source.target, source.status, source.reason),
                )

    def _record_changes(self, scan_id: int) -> int:
        previous = self._conn.execute(
            "SELECT id FROM scans WHERE status = 'succeeded' AND id < ? ORDER BY id DESC LIMIT 1",
            (scan_id,),
        ).fetchone()
        if previous is None:
            return 0
        previous_id = int(previous["id"])
        before = _entity_map(self._conn, previous_id)
        after = _entity_map(self._conn, scan_id)
        count = 0
        for key, payload in after.items():
            if key not in before:
                self._insert_change(scan_id, previous_id, key, "added", None, payload)
                count += 1
            elif before[key] != payload:
                self._insert_change(scan_id, previous_id, key, "modified", before[key], payload)
                count += 1
        for key, payload in before.items():
            if key not in after:
                self._insert_change(scan_id, previous_id, key, "removed", payload, None)
                count += 1
        return count

    def _insert_change(
        self,
        scan_id: int,
        previous_id: int,
        key: tuple[str, str],
        kind: str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO changes (scan_id, previous_scan_id, entity_kind, entity_key, change_kind, "
            "before_json, after_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                scan_id,
                previous_id,
                key[0],
                key[1],
                kind,
                None if before is None else json.dumps(before, sort_keys=True),
                None if after is None else json.dumps(after, sort_keys=True),
            ),
        )


def _entity_map(conn: sqlite3.Connection, scan_id: int) -> dict[tuple[str, str], dict[str, Any]]:
    rows = conn.execute(
        "SELECT kind, entity_key, payload FROM entities WHERE scan_id = ?",
        (scan_id,),
    ).fetchall()
    return {(row["kind"], row["entity_key"]): json.loads(row["payload"]) for row in rows}


def _entity_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = json.loads(row["payload"])
    return {"kind": row["kind"], "key": row["entity_key"], "payload": payload}


def _mask_payload(value: object) -> object:
    if isinstance(value, str):
        return mask_secrets(value)
    if isinstance(value, list):
        return [_mask_payload(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _mask_payload(item) for key, item in value.items()}
    return value


def _row_id(cursor: sqlite3.Cursor) -> int:
    if cursor.lastrowid is None:
        raise RuntimeError("insert did not return a row id")
    return int(cursor.lastrowid)


def _loads(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)
