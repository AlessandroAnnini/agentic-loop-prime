#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
exec uv run --project "$root" python -m agentic_loop_prime.adapters vscode
