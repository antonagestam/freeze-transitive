from collections.abc import Sequence, Mapping, Iterator
from dataclasses import dataclass
from typing import NewType

from typing_extensions import Self

from .parsers import take, take_sequence, parse


FQN = NewType("FQN", str)


@dataclass(frozen=True, slots=True)
class ConfiguredHook:
    id: str
    additional_dependencies: Sequence[str]

    @classmethod
    def parse(cls, unknown: object) -> Self:
        data = parse(unknown, Mapping)
        return cls(
            id=take(data, str, "id"),
            additional_dependencies=take_sequence(data, str, "additional_dependencies"),
        )

    def fully_qualified(self, repo: str) -> FQN:
        joined_dependencies = ",".join(sorted(self.additional_dependencies))
        return FQN(
            ":".join((repo, joined_dependencies)) if joined_dependencies else repo
        )


@dataclass(frozen=True, slots=True)
class ConfiguredRepo:
    repo: str
    rev: str
    hooks: Sequence[ConfiguredHook]

    @classmethod
    def parse(cls, unknown: object) -> Self:
        data = parse(unknown, Mapping)
        hooks_data = take(data, Sequence, "hooks")
        return cls(
            repo=take(data, str, "repo"),
            rev=take(data, str, "rev"),
            hooks=tuple(ConfiguredHook.parse(hook_data) for hook_data in hooks_data),
        )

    def repository_ids(self) -> Iterator[str]:
        seen = set()
        for hook in self.hooks:
            dependencies = hook.join_dependencies()
            fully_qualified = ":".join((self.repo, dependencies)) if dependencies else self.repo
            if fully_qualified in seen:
                continue
            seen.add(fully_qualified)
            yield fully_qualified
