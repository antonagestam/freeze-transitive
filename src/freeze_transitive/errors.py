class UserError(Exception):
    ...


class ConfigError(UserError):
    ...


class MissingKey(ConfigError):
    ...


class NoPython(RuntimeError):
    ...
