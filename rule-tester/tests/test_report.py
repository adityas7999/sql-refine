import json
from types import SimpleNamespace

from rule_tester.models import EquivalenceEvidence
from rule_tester.report import write_report


def test_report_is_redacted_and_omits_raw_samples(tmp_path):
    secret = "credential-that-must-never-appear"
    candidate = SimpleNamespace(
        rule_id="manual",
        classification="unclassified-human-candidate",
        strict_machine_preconditions=False,
        schema_agnostic_rule=False,
        original_sql="SELECT '" + secret + "'",
        candidate_sql="SELECT '" + secret + "'",
    )
    equivalence = EquivalenceEvidence(True, False, 1, 1, "EQUIVALENT")
    session = {
        "session": 1,
        "raw_samples_ms": {"original": [1.0], "candidate": [0.5]},
        "original": {"sample_count": 7, "median_ms": 1.0, "mean_ms": 1.0, "variance_ms2": 0.0, "p95_ms": 1.0},
        "candidate": {"sample_count": 7, "median_ms": 0.5, "mean_ms": 0.5, "variance_ms2": 0.0, "p95_ms": 0.5},
        "paired_win_rate_percent": 100.0,
        "median_improvement_percent": 50.0,
        "estimated_cost": {"original": 2.0, "candidate": 1.0},
        "cost_improvement_percent": 50.0,
    }
    benchmark = {"complete": True, "error_code": None, "sessions": [session, {**session, "session": 2}]}

    path = write_report(
        candidate=candidate,
        equivalence=equivalence,
        benchmark=benchmark,
        decision={"status": "rejected", "checks": {}},
        mysql_version="8.0.test",
        fingerprint="sha256:abc",
        output_root=tmp_path,
    )

    content = path.read_text(encoding="utf-8")
    document = json.loads(content)
    assert secret not in content
    assert "raw_samples_ms" not in content
    assert "original_sql" not in content
    assert "candidate_sql" not in content
    assert document["environment"]["schema_index_fingerprint"] == "sha256:abc"
