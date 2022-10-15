from __future__ import annotations

import sqlite3
import subprocess
import sys
from collections.abc import Iterable
from collections.abc import Iterator
from pathlib import Path
from sqlite3 import Cursor

import yaml

from .errors import ConfigError
from .errors import NoPython
from .schema import FQN
from .schema import Hook
from .schema import Repo
from .schema import Result
from functools import cache


@cache
def get_database_cursor() -> Cursor:
    path = (Path.home() / ".cache/pre-commit/db.db").resolve()
    connection = sqlite3.connect(str(path))
    return connection.cursor()


def get_repo_path(fqn: FQN, revision: str) -> Path:
    cursor = get_database_cursor()
    result = cursor.execute(
        """\
        SELECT path FROM repos
        WHERE repo = ? AND ref = ?
        LIMIT 1
        """,
        (fqn, revision),
    )
    (path,) = result.fetchone()
    return Path(path)


def read_configured_repos() -> Iterator[Repo]:
    path = (Path.cwd() / ".pre-commit-config.yaml").resolve()
    parsed = yaml.load(path.read_text(), Loader=yaml.CLoader)
    repos = parsed.get("repos", None)
    if not repos or not isinstance(repos, Iterable):
        raise ConfigError(
            "Missing, empty or malformed key `repos` in pre-commit config"
        )
    for repo_data in repos:
        yield Repo.parse(repo_data)


def get_unique_hooks() -> Iterator[tuple[Repo, Hook, FQN]]:
    for repo in read_configured_repos():
        seen = set[FQN]()
        for hook in repo.hooks:
            fqn = hook.fully_qualified(repo.repo)
            if fqn in seen:
                continue
            seen.add(fqn)
            yield repo, hook, fqn


def pip_freeze(python_path: Path) -> Iterator[str]:
    command = subprocess.Popen(
        (str(python_path), "-m", "pip", "freeze"),
        stdout=subprocess.PIPE,
    )
    with command as process:
        try:
            return_code = process.wait(timeout=10)
        except:  # noqa: E722 B001
            process.kill()
            raise
        # TODO: Handle
        assert return_code == 0
        assert process.stdout is not None

        for line in process.stdout.readlines():
            normalized = line.strip().decode()
            # Filter out reference to the installed hook itself.
            if "@ file" in normalized:
                continue
            yield normalized


def get_python_path(repo_path: Path) -> Path:
    for path in repo_path.glob("py_env*"):
        exec_path = path / "bin/python3"
        if exec_path.exists():
            return exec_path
    raise NoPython


def main() -> Result:
    result = Result.PASSING

    for repo, hook, fqn in get_unique_hooks():
        path = get_repo_path(fqn, repo.rev)

        try:
            python_path = get_python_path(path)
        except NoPython:
            print(f"Missing pip path for {hook.id}", file=sys.stderr)
            continue

        missing_entries = sorted(
            dependency
            for dependency in pip_freeze(python_path)
            if dependency not in hook.additional_dependencies
        )

        if missing_entries:
            result = Result.FAILING
            print(f"Missing entries for {hook.id}:", file=sys.stderr)
            for dependency in missing_entries:
                print(f"- {dependency!r}", file=sys.stderr)
        else:
            print(f"{hook.id}: OK!", file=sys.stderr)

    return result
