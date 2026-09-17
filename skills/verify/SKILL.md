---
name: prime-verify
description: >-
  Independent checker. HANDOFF verify means switch here. Do not edit app/.
  al-prime done --pass runs UNIT/E2E or SECURITY_* plus the findings-table
  gate or the judge checklist.
---

# Prime verify

Checker, not maker. `al-prime next` prints `HANDOFF verify` when build is done; that is the cue to stop building.

Substeps: `prove` → `security` → `judge`.

1. Confirm you did not change `app/`
2. Fill ADR-0005 commands if prove/security has nothing to run
3. On security: `--pass` runs `SECURITY_*` and writes `checks/tools.json`. Command failure is `DONE fail` (lock cleared). When commands pass and `security.md` is missing, the harness seeds the kit template (`**Status:** draft`, `**Secrets clean:** pending`). An unfilled report is `ERROR` and the lock stays so you can triage and `--pass` again. The harness never stamps `**Status:** pass`.
4. Close:

```bash
al-prime done --memory memory --pass
```

`--pass` runs the harness and stamps only if it agrees. Prove `--pass` writes `checks/prove.yaml` when UNIT/E2E exit 0. Judge `--pass` merges the feature into `develop` and bumps `VERSION` on `app/` only. `--fail` if you already know the check should not run. Never commits.

## Security report

Path: `memory/features/<id>/checks/security.md`

The tools harness does not invent findings rows. You copy scanner output into the tables. Critical/High must be `fixed` or `false_positive`. Every Medium needs a disposition (`fixed`, `accepted`, `false_positive`, `deferred`). Set `**Secrets clean:** yes` or `no`. Set `**Status:** pass` only after those rules hold. The gate reads that Status line, not the verdict checkboxes.

## Do not

- Edit `app/`
- Plant `tests_passed: true`
- Set `**Status:** pass` before findings are dispositioned
- Stay in the build skill after HANDOFF
