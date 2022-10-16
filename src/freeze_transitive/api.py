from __future__ import annotations

import copy
import sqlite3
import subprocess
import sys
from collections.abc import Iterable
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from sqlite3 import Cursor
from typing import NewType
from typing import TextIO

import yaml

from .errors import ConfigError
from .errors import NoPython
from .parsers import parse
from .parsers import take
from .schema import FQN
from .schema import Append
from .schema import Hook
from .schema import Repo
from .schema import Result


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


ParsedConfig = NewType("ParsedConfig", dict[object, object])


def parse_config() -> ParsedConfig:
    path = (Path.cwd() / ".pre-commit.yaml").resolve()
    return ParsedConfig(parse(yaml.load(path.read_text(), Loader=yaml.CLoader), dict))


def read_configured_repos(config: ParsedConfig) -> Iterator[Repo]:
    repos = config.get("repos", None)
    if not repos or not isinstance(repos, Iterable):
        raise ConfigError(
            "Missing, empty or malformed key `repos` in pre-commit config"
        )
    for repo_data in repos:
        yield Repo.parse(repo_data)


def get_unique_hooks(config: ParsedConfig) -> Iterator[tuple[Repo, Hook, FQN]]:
    for repo in read_configured_repos(config):
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
        # todo: Handle
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


def generate_operations(config: ParsedConfig) -> Iterator[Append]:
    for repo, hook, fqn in get_unique_hooks(config):
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
            print(f"Missing entries for {hook.id}:", file=sys.stderr)
            for dependency in missing_entries:
                print(f"- {dependency!r}", file=sys.stderr)
                yield Append(
                    repo=repo,
                    hook=hook,
                    value=dependency,
                )
        else:
            print(f"{hook.id}: OK!", file=sys.stderr)


def update_config(config: ParsedConfig, operations: Iterable[Append]) -> ParsedConfig:
    config = copy.deepcopy(config)
    repos = take(config, list, "repos")

    # Write pinned dependencies.
    for operation in operations:
        try:
            repo = next(
                repo
                for repo in repos
                if operation.repo.repo == take(repo, str, "repo")
                and operation.repo.rev == take(repo, str, "rev")
            )
        except StopIteration:
            raise RuntimeError(
                f"Failed finding repo for append operation {operation.repo.repo=} "
                f"{operation.repo.rev=}"
            )

        try:
            hook = next(
                hook
                for hook in take(repo, list, "hooks")
                if operation.hook.id == take(hook, str, "id")
            )
        except StopIteration:
            raise RuntimeError(
                f"Failed finding hook for append operation {operation.repo.repo=} "
                f"{operation.repo.rev=} {operation.hook.id=}"
            )

        assert isinstance(hook, dict)
        hook["additional_dependencies"] = [
            # Remove unpinned dependencies.
            *(
                dependency
                for dependency in hook.get("additional_dependencies", ())
                if "==" in dependency
            ),
            # Add the new pinned dependency.
            operation.value,
        ]

    return config


def write_config(config: ParsedConfig, outfile: TextIO) -> None:
    print(
        "# Note! This is an auto-generated file, do not make manual edits here.",
        file=outfile,
    )
    yaml.dump(config, outfile)


def main(outfile: TextIO | None) -> Result:
    result = Result.PASSING
    config = parse_config()
    operations = tuple(generate_operations(config))

    if outfile is not None:
        write_config(update_config(config, operations), outfile)

    return result
