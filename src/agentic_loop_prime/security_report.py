"""Security report gate: status, secrets, fingerprint, tools, dispositions."""

from __future__ import annotations

import re
from pathlib import Path

from agentic_loop_prime.fingerprint import baseline_digest
from agentic_loop_prime.paths import security_path

STATUS_PASS = re.compile(r"^\*\*Status:\*\*\s*pass\b", re.IGNORECASE | re.MULTILINE)
SECRETS_NOT_CLEAN = re.compile(r"\*\*Secrets clean:\*\*\s*no\b", re.I)
SECURITY_FINGERPRINT_LINE = re.compile(
    r"^\*\*App fingerprint:\*\*\s*([0-9a-fA-F]{16,})\s*$", re.MULTILINE
)
SECURITY_TABLE_ROW = re.compile(
    r"^\|\s*(?P<finding>[^|]+?)\s*\|\s*(?P<sev>[^|]+?)\s*\|(?P<rest>.*)$",
    re.MULTILINE,
)
SECURITY_OPEN_CRITICAL = re.compile(r"\b(critical|high)\b", re.I)
SECURITY_DISPOSITION_OK = {
    "fixed",
    "accepted",
    "false_positive",
    "deferred",
    "none",
    "n/a",
    "-",
}


def passing_security_markdown(digest: str, feature_id: str = "") -> str:
    """Minimal report that satisfies the parser when the harness is fresh."""
    title = f"# Security Report: {feature_id}\n\n" if feature_id else "# Security\n\n"
    return (
        f"{title}"
        f"**Status:** pass\n"
        f"**App fingerprint:** {digest}\n"
        f"**Secrets clean:** yes\n"
        "\n"
        "## Secrets scan\n"
        "\n"
        "| Finding | Severity | Path | Disposition |\n"
        "|---------|----------|------|-------------|\n"
        "| (none) | | | |\n"
        "\n"
        "## SCA (dependencies)\n"
        "\n"
        "| Finding | Severity | Package | Disposition |\n"
        "|---------|----------|---------|-------------|\n"
        "| (none) | | | |\n"
        "\n"
        "## Medium / Low findings\n"
        "\n"
        "| Finding | Severity | Path | Disposition | Rationale |\n"
        "|---------|----------|------|-------------|----------|\n"
        "| (none) | | | | |\n"
    )


def _security_table_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for m in SECURITY_TABLE_ROW.finditer(text):
        finding = m.group("finding").strip()
        sev = m.group("sev").strip()
        rest = m.group("rest")
        if finding.lower() in {"finding", "---", ""} or set(finding) <= {"-"}:
            continue
        if sev.lower() in {"severity", "---"} or set(sev) <= {"-"}:
            continue
        disposition = _disposition_from_rest(rest)
        rows.append(
            {
                "finding": finding,
                "severity": sev,
                "disposition": disposition.lower(),
            }
        )
    return rows


def _disposition_from_rest(rest: str) -> str:
    """Disposition is the last meaningful column after Finding|Severity.

    Keep empty cells so `| Medium | path | |` is missing, not `path`.
    """
    cols = [c.strip() for c in rest.split("|")]
    if cols and cols[-1] == "":
        cols = cols[:-1]
    if not cols:
        return ""
    if len(cols) >= 3:
        return cols[1]
    if len(cols) == 2:
        return cols[-1]
    return cols[0]


def security_report_failure_reason(memory: Path, feature_id: str) -> str | None:
    """Return None when the security gate passes; else a short failure reason."""
    path = security_path(memory, feature_id)
    if not path.is_file():
        return "missing security report"
    text = path.read_text(encoding="utf-8")
    if not STATUS_PASS.search(text):
        return "status is not pass"
    if SECRETS_NOT_CLEAN.search(text):
        return "secrets not clean"
    digest = baseline_digest(memory, feature_id)
    if not digest:
        return "missing app fingerprint baseline"
    m = SECURITY_FINGERPRINT_LINE.search(text)
    if not m:
        return "missing or mismatched **App fingerprint:** line"
    if m.group(1).lower() != digest.lower():
        return "security report fingerprint does not match baseline"
    from agentic_loop_prime.tools import security_tools_ok

    if not security_tools_ok(memory, feature_id):
        return "security tools harness missing/stale/failed"
    for row in _security_table_rows(text):
        finding = row["finding"].lower()
        if finding in {"(none)", "none"}:
            continue
        sev = row["severity"].lower()
        disp = row["disposition"].strip().lower()
        if SECURITY_OPEN_CRITICAL.search(sev):
            if disp not in {"fixed", "false_positive"}:
                return (
                    f"open {row['severity']} without fixed/false_positive: "
                    f"{row['finding']}"
                )
        if "medium" in sev:
            if not disp or disp in {"", "open", "todo", "tbd"}:
                return f"Medium finding missing Disposition: {row['finding']}"
            if disp not in SECURITY_DISPOSITION_OK:
                return f"Medium Disposition invalid: {row['finding']} -> {disp}"
    return None


def security_report_passed(memory: Path, feature_id: str) -> bool:
    return security_report_failure_reason(memory, feature_id) is None
