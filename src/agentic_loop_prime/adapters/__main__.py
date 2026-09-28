"""Run the adapter Prime selected."""

from __future__ import annotations

import sys

from agentic_loop_prime.adapters.claude import run as run_claude
from agentic_loop_prime.adapters.cursor import run as run_cursor
from agentic_loop_prime.adapters.vscode import run as run_vscode

_RUNNERS = {
    "cursor": run_cursor,
    "claude": run_claude,
    "vscode": run_vscode,
}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] not in _RUNNERS:
        print(
            "usage: python -m agentic_loop_prime.adapters cursor|claude|vscode",
            file=sys.stderr,
        )
        return 2
    return _RUNNERS[args[0]]()


if __name__ == "__main__":
    raise SystemExit(main())
