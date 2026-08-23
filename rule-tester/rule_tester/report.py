"""Redacted benchmark evidence reports."""

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from .bootstrap import REPOSITORY_ROOT


def _aggregate_session(session: dict) -> dict:
    return {
        "session": session["session"],
        "original": session["original"],
        "candidate": session["candidate"],
        "paired_win_rate_percent": session["paired_win_rate_percent"],
        "median_improvement_percent": session["median_improvement_percent"],
        "estimated_cost": session["estimated_cost"],
        "cost_improvement_percent": session["cost_improvement_percent"],
        "composite_improvement_percent": session["composite_improvement_percent"],
    }


def write_report(*, candidate, equivalence, benchmark: dict, decision: dict, mysql_version: str, fingerprint: str, output_root: Path | None = None) -> Path:
    destination = output_root or (REPOSITORY_ROOT / "rule-test-results")
    destination.mkdir(parents=True, exist_ok=True)
    document = {
        "format_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "rule": {
            "id": candidate.rule_id,
            "classification": candidate.classification,
            "strict_machine_checkable_preconditions": candidate.strict_machine_preconditions,
            "schema_agnostic_rule": candidate.schema_agnostic_rule,
        },
        "equivalence": {
            "equivalent": equivalence.equivalent,
            "ordered_comparison": equivalence.ordered,
            "original_row_count": equivalence.original_row_count,
            "candidate_row_count": equivalence.candidate_row_count,
            "reason_code": equivalence.reason_code,
        },
        "environment": {
            "mysql_version": mysql_version,
            "schema_index_fingerprint": fingerprint,
        },
        "benchmark": {
            "complete": benchmark.get("complete", False),
            "error_code": benchmark.get("error_code"),
            "warmup_count": benchmark.get("warmup_count"),
            "configured_samples_per_query_per_session": benchmark.get(
                "configured_samples_per_query_per_session"
            ),
            "sessions": [_aggregate_session(item) for item in benchmark.get("sessions", [])],
        },
        "promotion_decision": decision,
        "notice": "Human review is required; this report never modifies or enables a rule.",
    }
    filename = "rule-benchmark-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8] + ".json"
    path = destination / filename
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
