import sys

from freeze_transitive.errors import UserError
from .fetch import main


try:
    main()
except UserError as exc:
    print(f"{exc.__class__.__qualname__}: {exc}", file=sys.stderr)
    exit(1)
