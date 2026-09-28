"""Editor adapters. `python -m agentic_loop_prime.adapters cursor|claude|vscode`."""

from agentic_loop_prime.adapters.claude import run as run_claude
from agentic_loop_prime.adapters.cursor import run as run_cursor
from agentic_loop_prime.adapters.vscode import run as run_vscode

__all__ = ["run_claude", "run_cursor", "run_vscode"]
