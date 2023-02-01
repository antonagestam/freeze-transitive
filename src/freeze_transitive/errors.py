class UserError(Exception):
    ...


class ConfigError(UserError):
    ...


class MissingKey(ConfigError):
    ...


class NoPython(RuntimeError):
    ...


class NoRepo(RuntimeError):
    ...


class LocalRepo(Exception):
    ...


class CacheMiss(RuntimeError):
    ...
