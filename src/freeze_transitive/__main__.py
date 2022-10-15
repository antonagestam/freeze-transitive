import sys

from typing_extensions import assert_never

from freeze_transitive.errors import UserError

from . import api
from .schema import Result

if __name__ == "__main__":
    try:
        result = api.main()
    except UserError as exc:
        print(f"{exc.__class__.__qualname__}: {exc}", file=sys.stderr)
        result = Result.ERROR

    match result:
        case Result.PASSING:
            pass
        case Result.FAILING:
            exit(1)
        case Result.ERROR:
            exit(2)
        case not_exhaustive:
            assert_never(not_exhaustive)
