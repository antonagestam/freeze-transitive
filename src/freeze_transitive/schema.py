import enum
from collections.abc import Sequence
from dataclasses import dataclass
from typing import NewType
from typing import TypeVar

from .parsers import parse
from .parsers import take
from .parsers import take_sequence

FQN = NewType("FQN", str)

# TODO: Use typing_extensions.Self when implemented in mypy.
HookSelf = TypeVar("HookSelf", bound="Hook")
RepoSelf = TypeVar("RepoSelf", bound="Repo")


@dataclass(frozen=True, slots=True)
class Hook:
    id: str
    additional_dependencies: Sequence[str]

    @classmethod
    def parse(cls: type[HookSelf], unknown: object) -> HookSelf:
        data = parse(unknown, dict)
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
class Repo:
    repo: str
    rev: str
    hooks: Sequence[Hook]

    @classmethod
    def parse(cls: type[RepoSelf], unknown: object) -> RepoSelf:
        data = parse(unknown, dict)
        hooks_data = take(data, list, "hooks")
        return cls(
            repo=take(data, str, "repo"),
            rev=take(data, str, "rev"),
            hooks=tuple(Hook.parse(hook_data) for hook_data in hooks_data),
        )


@enum.unique
class Result(enum.Enum):
    PASSING = enum.auto()
    FAILING = enum.auto()
    ERROR = enum.auto()