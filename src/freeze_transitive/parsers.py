from collections.abc import Mapping
from collections.abc import Sequence
from typing import TypeVar

from .errors import ConfigError
from .errors import MissingKey

T = TypeVar("T")


def parse(value: object, type_: type[T]) -> T:
    if not isinstance(value, type_):
        raise ConfigError(f"Malformed data, expected {type_}")
    return value


def take(data: Mapping[object, object], type_: type[T], key: str) -> T:
    try:
        value = data[key]
    except KeyError as exc:
        raise MissingKey(f"Missing required key: {key!r}") from exc
    return parse(value, type_)


def take_sequence(
    data: Mapping[object, object],
    type_: type[T],
    key: str,
    missing_as_empty: bool = True,
) -> tuple[T, ...]:
    try:
        sequence = data[key]
    except KeyError as exc:
        if missing_as_empty:
            return ()
        raise MissingKey(f"Missing required key: {key!r}") from exc
    if not isinstance(sequence, Sequence):
        raise ConfigError(f"Expected sequence at key {key!r}, got {type(sequence)}")
    return tuple(parse(value, type_) for value in sequence)
