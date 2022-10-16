import sqlite3
from functools import cache
from pathlib import Path
from sqlite3 import Connection

from freeze_transitive.errors import CacheMiss
from freeze_transitive import __version__


def _create_table(connection: Connection) -> None:
    cursor = connection.cursor()
    cursor.execute(
        """\
        CREATE TABLE IF NOT EXISTS state_cache (
            version TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (version, key)
        );
        """
    )


@cache
def _get_database_connection() -> Connection:
    path = (Path.home() / ".cache/pre-commit-freeze-transitive/db.db").resolve()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    _create_table(connection)
    return connection


def write(key: str, value: str) -> None:
    connection = _get_database_connection()
    cursor = connection.cursor()
    cursor.execute(
        """\
        INSERT INTO state_cache (version, key, value)
        VALUES (?, ?, ?)
        ON CONFLICT(version, key) DO UPDATE SET
            value=excluded.value;
        """,
        (__version__, key, value),
    )
    connection.commit()


def read(key: str) -> str:
    cursor = _get_database_connection().cursor()
    result = cursor.execute(
        """\
        SELECT value FROM state_cache
        WHERE version = ? AND key = ?
        LIMIT 1
        """,
        (__version__, key,),
    )
    row = result.fetchone()
    if row is None:
        raise CacheMiss
    (value,) = row
    assert isinstance(value, str)
    return value


def compare(key: str, value: str) -> bool:
    try:
        return read(key) == value
    except CacheMiss:
        return False
