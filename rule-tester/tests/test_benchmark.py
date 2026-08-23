from types import SimpleNamespace
from contextlib import contextmanager

import pytest

from rule_tester import benchmark
from rule_tester.benchmark import composite_improvement, promotion_decision, sample_statistics
from rule_tester.models import QueryOutput
from rule_tester.models import EquivalenceEvidence


def _session(number, win_rate=100.0, median_improvement=20.0, cost_improvement=12.0):
    return {
        "session": number,
        "original": {
            "sample_count": 7,
            "median_ms": 10.0,
            "mean_ms": 10.0,
            "variance_ms2": 1.0,
            "p95_ms": 11.0,
        },
        "candidate": {
            "sample_count": 7,
            "median_ms": 8.0,
            "mean_ms": 8.0,
            "variance_ms2": 0.5,
            "p95_ms": 9.0,
        },
        "paired_win_rate_percent": win_rate,
        "median_improvement_percent": median_improvement,
        "estimated_cost": {"original": 100.0, "candidate": 88.0},
        "cost_improvement_percent": cost_improvement,
        "composite_improvement_percent": composite_improvement(
            median_improvement, cost_improvement
        ),
    }


def test_statistics_include_requested_metrics():
    result = sample_statistics([1, 2, 3, 4, 5, 6, 7])
    assert result["median_ms"] == 4
    assert result["mean_ms"] == 4
    assert result["variance_ms2"] == pytest.approx(4.6666666667)
    assert result["p95_ms"] == 7


def test_all_thresholds_are_required_for_eligibility():
    equivalence = EquivalenceEvidence(True, False, 10, 10, "EQUIVALENT")
    candidate = SimpleNamespace(strict_machine_preconditions=True, schema_agnostic_rule=True)
    benchmark = {"complete": True, "sessions": [_session(1), _session(2)]}

    decision = promotion_decision(equivalence, benchmark, candidate)

    assert decision["status"] == "eligible for human rule review"
    assert all(decision["checks"].values())


def test_one_inconsistent_session_rejects_candidate():
    equivalence = EquivalenceEvidence(True, False, 10, 10, "EQUIVALENT")
    candidate = SimpleNamespace(strict_machine_preconditions=True, schema_agnostic_rule=True)
    benchmark = {"complete": True, "sessions": [_session(1), _session(2, win_rate=71.0)]}

    decision = promotion_decision(equivalence, benchmark, candidate)

    assert decision["status"] == "rejected"
    assert not decision["checks"]["paired_win_rate_at_least_80_percent"]


def test_composite_score_must_be_strictly_greater_than_five_percent():
    equivalence = EquivalenceEvidence(True, False, 10, 10, "EQUIVALENT")
    candidate = SimpleNamespace(strict_machine_preconditions=True, schema_agnostic_rule=True)
    benchmark = {
        "complete": True,
        "sessions": [
            _session(1, median_improvement=5.0, cost_improvement=5.0),
            _session(2, median_improvement=5.0, cost_improvement=5.0),
        ],
    }

    decision = promotion_decision(equivalence, benchmark, candidate)

    assert decision["status"] == "rejected"
    assert not decision["checks"]["composite_improvement_greater_than_5_percent"]


def test_manual_candidate_is_never_automatically_eligible():
    equivalence = EquivalenceEvidence(True, False, 10, 10, "EQUIVALENT")
    candidate = SimpleNamespace(strict_machine_preconditions=False, schema_agnostic_rule=False)
    benchmark = {"complete": True, "sessions": [_session(1), _session(2)]}

    decision = promotion_decision(equivalence, benchmark, candidate)

    assert decision["status"] == "rejected"


def test_execution_order_alternates_and_second_session_is_reversed(monkeypatch):
    calls = []

    @contextmanager
    def fake_connect(config, timeout_seconds):
        yield object()

    def fake_execute(connection, query, max_rows):
        calls.append(query)
        return QueryOutput((("value", 3),), ((1,),))

    monkeypatch.setattr(benchmark, "connect", fake_connect)
    monkeypatch.setattr(benchmark, "execute_complete", fake_execute)
    monkeypatch.setattr(benchmark, "explain_cost", lambda connection, query: 1.0)
    monkeypatch.setattr(benchmark.time, "perf_counter", iter(range(1000)).__next__)

    benchmark._session(
        object(),
        "original",
        "candidate",
        session_index=0,
        warmups=0,
        samples=7,
        timeout_seconds=1,
        max_rows=10,
    )
    first_session = calls[:14]
    calls.clear()
    benchmark._session(
        object(),
        "original",
        "candidate",
        session_index=1,
        warmups=0,
        samples=7,
        timeout_seconds=1,
        max_rows=10,
    )

    assert first_session[:4] == ["original", "candidate", "candidate", "original"]
    assert calls[:4] == ["candidate", "original", "original", "candidate"]
