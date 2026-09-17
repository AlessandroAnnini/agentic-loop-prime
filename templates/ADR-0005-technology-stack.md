# ADR-0005: Technology Stack

**Status:** accepted  
**Date:** YYYY-MM-DD

## Context

Agents need a single declared stack so build and verify do not invent frameworks or scanners.

## Decision

| Layer | Choice | Command |
|-------|--------|---------|
| Language | | |
| Package manager | | |
| App layout | `app/` (default) | |
| Unit / API tests | | `$UNIT_TEST_CMD` |
| E2E / acceptance | user journey (CLI argv, browser, or local fixture) | `$E2E_TEST_CMD` |
| Secrets scan | real scanner; fail if missing | `$SECURITY_SECRETS_CMD` |
| SCA (dependencies) | | `$SECURITY_SCA_CMD` |
| SAST | | `$SECURITY_SAST_CMD` |
| Lint / format | | |

`E2E_TEST_CMD` and `SECURITY_SECRETS_CMD` must not be `true`, `:`, or `echo`. E2E must differ from UNIT. Live-only hosts still need a local fixture or contract, not a no-op.

Example (replace with this project's tools):

```bash
export UNIT_TEST_CMD='python3 -c "print(1)"'
export E2E_TEST_CMD='python3 -c "print(2)"'
export SECURITY_SECRETS_CMD='gitleaks detect --source app --no-banner'
export SECURITY_SCA_CMD="true"
export SECURITY_SAST_CMD="true"
```

`al-prime done --pass` on verify/prove reads UNIT/E2E and writes `memory/features/<id>/checks/harness.json`.  
`al-prime done --pass` on verify/security reads SECURITY_* and writes `checks/tools.json`.

All three SECURITY_* exports are required. SCA/SAST may be a documented no-op until a tool exists. Secrets must be a real scan.

## Consequences

- Changing stack mid-program requires updating this ADR and re-signing affected briefs if acceptance criteria change.
