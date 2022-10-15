from __future__ import annotations

from typing import Iterable, Iterator
import sqlite3
import yaml
from pathlib import Path

from .errors import ConfigError
from .schema import ConfiguredRepo, ConfiguredHook, FQN


def get_repo_path(fqn: FQN, revision: str) -> Path:
    path = (Path.home() / ".cache/pre-commit/db.db").resolve()
    con = sqlite3.connect(str(path))
    cur = con.cursor()
    res = cur.execute(
        """\
        SELECT path FROM repos
        WHERE repo = ? AND ref = ?
        LIMIT 1
        """,
        (fqn, revision)
    )
    path, = res.fetchone()
    return Path(path)


def read_configured_repos() -> Iterator[ConfiguredRepo]:
    path = (Path().home() / "projects/phantom-types/.pre-commit-config.yaml").resolve()
    parsed = yaml.load(path.read_text(), Loader=yaml.CLoader)
    repos = parsed.get("repos", None)
    if not repos or not isinstance(repos, Iterable):
        raise ConfigError("Missing, empty or malformed key `repos` in pre-commit config")
    for repo_data in repos:
        yield ConfiguredRepo.parse(repo_data)


def get_unique_hooks() -> Iterator[tuple[ConfiguredRepo, ConfiguredHook, FQN]]:
    for repo in read_configured_repos():
        seen = set[FQN]()
        for hook in repo.hooks:
            fqn = hook.fully_qualified(repo.repo)
            if fqn in seen:
                continue
            seen.add(fqn)
            yield repo, hook, fqn


def main() -> None:
    for repo, hook, fqn in get_unique_hooks():
        print(fqn)
        print(f"{hook.id=}")
        path = get_repo_path(fqn, repo.rev)
        print(f"{path=}")
