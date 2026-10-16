"""Migration loader ignores AppleDouble junk and requires UTF-8 SQL."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from atlas.storage.db import apply_migrations, migration_paths, read_migration_sql


def test_appledouble_sql_files_are_ignored(tmp_path: Path) -> None:
    (tmp_path / "001_inventory.sql").write_text(
        "CREATE TABLE ok (id INTEGER PRIMARY KEY);\n", encoding="utf-8"
    )
    # Binary AppleDouble-style junk that used to crash utf-8 decode.
    (tmp_path / "._001_inventory.sql").write_bytes(b"\x00\x05\x16\x07" + b"\xa3" * 60)
    (tmp_path / "not_a_migration.sql").write_text("SELECT 1;\n", encoding="utf-8")

    names = [path.name for path in migration_paths(tmp_path)]
    assert names == ["001_inventory.sql"]

    conn = sqlite3.connect(":memory:")
    apply_migrations(conn, tmp_path)
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='ok'").fetchone()
    versions = [row[0] for row in conn.execute("SELECT version FROM schema_migrations")]
    assert versions == ["001_inventory.sql"]
    conn.close()


def test_non_utf8_named_migration_reports_the_path(tmp_path: Path) -> None:
    path = tmp_path / "006_bad.sql"
    path.write_bytes(b"CREATE TABLE x (id INTEGER); \xa3 broken")
    with pytest.raises(UnicodeDecodeError) as caught:
        read_migration_sql(path)
    assert "006_bad.sql" in caught.value.reason
