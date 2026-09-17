#!/usr/bin/env bash
# One unattended skill turn for Claude Code. Writes only. Prime closes the frame.
# Intended isolation when ALP_POLICY_FILE has app_writable=false:
#   claude --disallowedTools "Edit(app/**)" -p "$(cat "$ALP_PROMPT_FILE")"
set -euo pipefail

if ! command -v claude >/dev/null 2>&1; then
  echo "claude is not on PATH" >&2
  exit 1
fi

if [[ -z "${ALP_PROMPT_FILE:-}" ]]; then
  echo "ALP_PROMPT_FILE is required" >&2
  exit 1
fi

if [[ ! -f "$ALP_PROMPT_FILE" ]]; then
  echo "ALP_PROMPT_FILE is not a file: $ALP_PROMPT_FILE" >&2
  exit 1
fi

app_writable="true"
if [[ -n "${ALP_POLICY_FILE:-}" && -f "$ALP_POLICY_FILE" ]]; then
  if parsed="$(
    python3 -c '
import json, sys
path = sys.argv[1]
data = json.load(open(path, encoding="utf-8"))
print("true" if data.get("app_writable", True) else "false")
' "$ALP_POLICY_FILE" 2>/dev/null
  )"; then
    app_writable="$parsed"
  else
    echo "WARN: could not read ALP_POLICY_FILE; running claude -p without deny-write" >&2
  fi
fi

args=()
if [[ "$app_writable" == "false" ]]; then
  args+=(--disallowedTools "Edit(app/**)")
fi
args+=(-p "$(cat "$ALP_PROMPT_FILE")")

exec claude "${args[@]}"
