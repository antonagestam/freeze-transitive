import argparse
import sys
from pathlib import Path

from typing_extensions import assert_never

from freeze_transitive.errors import UserError

from . import api
from .schema import Result

parser = argparse.ArgumentParser(
    description="Freeze transitive pre-commit dependencies in Python hooks.",
)
# parser.add_argument(
#     "--stdout",
#     action="store_true",
#     help="Write locked file to stdout",
# )
parser.add_argument(
    "--outfile",
    type=Path,
    default=Path.cwd() / ".pre-commit-config.yaml",
)


if __name__ == "__main__":
    args = parser.parse_args()
    outfile_path: Path = args.outfile.resolve()

    with args.outfile.open("w") as outfile:
        try:
            result = api.main(outfile=outfile)
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
