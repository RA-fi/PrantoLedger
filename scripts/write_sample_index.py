"""Build samples/INDEX.md from the generated JSON files."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT / "samples"

PUBLIC_ORDER = [f"sample_{i:02d}.json" for i in range(1, 11)]
EDGE_ORDER = [
    "edge_injection_fallback.json",
    "edge_phishing.json",
    "edge_phishing_bangla.json",
    "edge_empty_complaint_400.json",
    "edge_invalid_enum_400.json",
    "edge_reversed_history.json",
    "edge_banglish_mixed.json",
]


def _load(name: str) -> dict:
    return json.loads((SAMPLES_DIR / name).read_text(encoding="utf-8"))


def _row(name: str, *, is_edge: bool) -> str:
    data = _load(name)
    req = data.get("request", {})
    res = data.get("response", {})
    desc = data.get("_meta", {}).get("description", "").strip()
    ticket = req.get("ticket_id", "—")
    complaint = (req.get("complaint") or "").replace("\n", " ").strip()
    if len(complaint) > 80:
        complaint = complaint[:77] + "..."

    if isinstance(res, dict) and "case_type" in res:
        verdict = res.get("evidence_verdict", "—")
        case_type = res.get("case_type", "—")
        severity = res.get("severity", "—")
        dept = res.get("department", "—")
        review = "yes" if res.get("human_review_required") else "no"
        return (
            f"| `{name}` | `{ticket}` | `{case_type}` | `{severity}` | `{dept}` "
            f"| `{verdict}` | `{review}` | {complaint} |"
        )

    # Error-shape responses
    err = res.get("error") if isinstance(res, dict) else None
    if isinstance(err, dict) and err.get("error") == "invalid_request":
        return (
            f"| `{name}` | `{ticket}` | `invalid_request` | — | — | — | — "
            f"| _HTTP 400 — validation error_ |"
        )
    return (
        f"| `{name}` | `{ticket}` | — | — | — | — | — | _non-2xx response_ |"
    )


def main() -> int:
    lines: list[str] = []
    lines.append("# Sample Round-Trips")
    lines.append("")
    lines.append(
        "Every file below was produced by POSTing the request to the live "
        "`/analyze-ticket` endpoint (FastAPI TestClient) and capturing both sides "
        "of the round-trip. The service is run with no `GROQ_*` env vars, so all "
        "responses are deterministic and template-only."
    )
    lines.append("")
    lines.append("Each file has the shape:")
    lines.append("")
    lines.append("```json")
    lines.append("{")
    lines.append('  "_meta":        { "source": "...", "description": "..." },')
    lines.append('  "request":      { ...AnalyzeTicketRequest... },')
    lines.append('  "response":     { ...AnalyzeTicketResponse | error... },')
    lines.append('  "expected_output": { ...rubric expectation from the PRD... }')
    lines.append("}")
    lines.append("```")
    lines.append("")
    lines.append("## Public sample cases (PRD §16)")
    lines.append("")
    lines.append("| File | Ticket | Case type | Severity | Department | Evidence | Human review | Complaint (truncated) |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for name in PUBLIC_ORDER:
        lines.append(_row(name, is_edge=False))

    lines.append("")
    lines.append("## Adversarial / edge-case samples")
    lines.append("")
    lines.append("| File | Ticket | Case type | Severity | Department | Evidence | Human review | Complaint (truncated) |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for name in EDGE_ORDER:
        lines.append(_row(name, is_edge=True))

    lines.append("")
    lines.append("## How to regenerate")
    lines.append("")
    lines.append("```bash")
    lines.append("python scripts/generate_samples.py")
    lines.append("```")
    lines.append("")
    lines.append("Re-running overwrites the files. The script is idempotent "
                 "and uses an isolated SQLite file at `data/samples.auditor.db` "
                 "so it does not pollute the dev database.")
    lines.append("")
    out = SAMPLES_DIR / "INDEX.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())