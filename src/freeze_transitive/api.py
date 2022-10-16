from __future__ import annotations

import copy
import hashlib
import re
import sqlite3
import subprocess
import sys
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from sqlite3 import Cursor
from typing import Final
from typing import NewType
from typing import TextIO

import yaml

from . import state_cache
from .errors import ConfigError
from .errors import LocalRepo
from .errors import NoPython
from .parsers import parse
from .parsers import take
from .schema import FQN
from .schema import Checksum
from .schema import Hook
from .schema import Replace
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


def parse_config(path: Path) -> ParsedConfig:
    return ParsedConfig(parse(yaml.load(path.read_text(), Loader=yaml.CLoader), dict))


def read_configured_repos(config: ParsedConfig) -> Iterator[Repo]:
    repos = config.get("repos", None)
    if not repos or not isinstance(repos, Iterable):
        raise ConfigError(
            "Missing, empty or malformed key `repos` in pre-commit config"
        )
    for repo_data in repos:
        try:
            yield Repo.parse(repo_data)
        except LocalRepo:
            print("Skipping local repo", file=sys.stderr)


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


def generate_operations(
    config: ParsedConfig,
    exclude_dependency: str | None,
) -> Iterator[Replace]:
    for repo, hook, fqn in get_unique_hooks(config):
        path = get_repo_path(fqn, repo.rev)

        try:
            python_path = get_python_path(path)
        except NoPython:
            print(f"Missing Python path for {hook.id}", file=sys.stderr)
            continue

        dependencies = tuple(
            dependency
            for dependency in pip_freeze(python_path)
            if (
                exclude_dependency is None
                or not dependency.startswith(f"{exclude_dependency}=")
            )
        )

        if not dependencies:
            continue

        yield Replace(repo=repo, hook=hook, dependencies=dependencies)


version_pattern: Final = re.compile(r"^(?P<name>[\w\-_]+)[<>=]{2}.*$")


def index_dependencies(dependencies: Iterable[str]) -> dict[str, str]:
    return {
        match.group("name"): dependency
        for dependency in dependencies
        if (match := version_pattern.fullmatch(dependency))
    }


def merge_dependencies(
    first_hand: Sequence[str],
    frozen: Sequence[str],
) -> Iterable[str]:
    indexed_first_hand = index_dependencies(first_hand)
    indexed_frozen = index_dependencies(frozen)

    for name, dependency in indexed_first_hand.items():
        if name not in indexed_frozen:
            yield dependency
    yield from frozen


def update_config(config: ParsedConfig, operations: Iterable[Replace]) -> ParsedConfig:
    config = copy.deepcopy(config)
    repos = take(config, list, "repos")

    # Write pinned dependencies.
    for operation in operations:
        try:
            repo = next(
                repo
                for repo in repos
                if operation.repo.repo == repo.get("repo")
                and operation.repo.rev == repo.get("rev")
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
        hook["additional_dependencies"] = sorted(
            merge_dependencies(
                first_hand=hook.get("additional_dependencies", ()),
                frozen=operation.dependencies,
            )
        )

    return config


def write_config(config: ParsedConfig, outfile: TextIO) -> None:
    print(
        "# Note! This is an auto-generated file, do not make manual edits here.",
        file=outfile,
    )
    yaml.dump(config, outfile)


def get_checksum(path: Path) -> Checksum:
    return Checksum(hashlib.sha512(path.read_bytes()).hexdigest())


def main(
    outfile_path: Path | None,
    infile_path: Path,
    exclude_dependency: str | None,
    use_cache: bool,
) -> Result:
    outfile_pre_checksum = (
        get_checksum(outfile_path) if outfile_path is not None else None
    )
    state_checksum = f"{get_checksum(infile_path)}-{exclude_dependency=}"

    if (
        use_cache
        and outfile_pre_checksum
        and state_cache.compare(outfile_pre_checksum, state_checksum)
    ):
        print(
            "Found cache match for current state, skipping processing", file=sys.stderr
        )
        return Result.PASSING

    config = parse_config(infile_path)
    operations = tuple(generate_operations(config, exclude_dependency))

    if outfile_path is not None:
        with outfile_path.open("w") as outfile:
            write_config(update_config(config, operations), outfile)

        outfile_post_checksum = get_checksum(outfile_path)

        if outfile_pre_checksum == outfile_post_checksum:
            if use_cache:
                state_cache.write(outfile_post_checksum, state_checksum)
            return Result.PASSING

        return Result.FAILING

    return Result.PASSING if len(operations) == 0 else Result.FAILING
