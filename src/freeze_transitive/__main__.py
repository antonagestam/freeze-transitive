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
parser.add_argument(
    "--infile",
    type=Path,
    default=Path.cwd() / ".pre-commit-template.yaml",
)
parser.add_argument(
    "--outfile",
    type=Path,
    default=Path.cwd() / ".pre-commit-config.yaml",
)
parser.add_argument(
    "--exclude-dependency",
    type=str,
    default=None,
)

if __name__ == "__main__":
    args = parser.parse_args()
    outfile_path: Path = args.outfile.resolve()
    infile_path: Path = args.infile.resolve()
    exclude_dependency: str | None = args.exclude_dependency

    print(f"Outfile: {str(outfile_path)!r}", file=sys.stderr)
    print(f"Infile: {str(infile_path)!r}", file=sys.stderr)

    try:
        result = api.main(outfile_path, infile_path, exclude_dependency)
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
