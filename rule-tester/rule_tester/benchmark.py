"""Two-session alternating benchmark protocol and promotion decision."""

import math
import statistics
import time

from .bootstrap import BACKEND_ROOT  # noqa: F401
from .mysql_runtime import QueryExecutionFailure, connect, execute_complete, explain_cost
from analyzer import COST_WEIGHT, TIME_WEIGHT


def _percentile_95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def sample_statistics(values: list[float]) -> dict:
    return {
        "sample_count": len(values),
        "median_ms": statistics.median(values),
        "mean_ms": statistics.mean(values),
        "variance_ms2": statistics.variance(values) if len(values) > 1 else 0.0,
        "p95_ms": _percentile_95(values),
    }


def improvement_percent(original: float | None, candidate: float | None) -> float | None:
    if original is None or candidate is None or original <= 0:
        return None
    return (original - candidate) / original * 100.0


def composite_improvement(runtime_improvement: float | None, cost_improvement: float | None) -> float | None:
    if runtime_improvement is None or cost_improvement is None:
        return None
    return runtime_improvement * TIME_WEIGHT + cost_improvement * COST_WEIGHT


def _timed_query(connection, query: str, max_rows: int) -> float:
    started = time.perf_counter()
    output = execute_complete(connection, query, max_rows=max_rows)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if output.truncated:
        raise QueryExecutionFailure("RESULT_TRUNCATED")
    return elapsed_ms


def _session(config, original: str, candidate: str, *, session_index: int, warmups: int, samples: int, timeout_seconds: int, max_rows: int) -> dict:
    collected = {"original": [], "candidate": []}
    queries = {"original": original, "candidate": candidate}
    with connect(config, timeout_seconds=timeout_seconds) as connection:
        costs = {
            "original": explain_cost(connection, original),
            "candidate": explain_cost(connection, candidate),
        }
        for round_index in range(warmups + samples):
            original_first = (round_index + session_index) % 2 == 0
            order = ("original", "candidate") if original_first else ("candidate", "original")
            pair = {}
            for label in order:
                pair[label] = _timed_query(connection, queries[label], max_rows)
            if round_index >= warmups:
                collected["original"].append(pair["original"])
                collected["candidate"].append(pair["candidate"])

    original_stats = sample_statistics(collected["original"])
    candidate_stats = sample_statistics(collected["candidate"])
    wins = sum(
        candidate_time < original_time
        for original_time, candidate_time in zip(collected["original"], collected["candidate"])
    )
    median_improvement = improvement_percent(
        original_stats["median_ms"], candidate_stats["median_ms"]
    )
    cost_improvement = improvement_percent(costs["original"], costs["candidate"])
    return {
        "session": session_index + 1,
        "raw_samples_ms": collected,
        "original": original_stats,
        "candidate": candidate_stats,
        "paired_win_rate_percent": wins / samples * 100.0,
        "median_improvement_percent": median_improvement,
        "estimated_cost": costs,
        "cost_improvement_percent": cost_improvement,
        "composite_improvement_percent": composite_improvement(
            median_improvement, cost_improvement
        ),
    }


def run_benchmark(config, original: str, candidate: str, *, warmups: int, samples: int, timeout_seconds: int, max_rows: int) -> dict:
    if warmups < 0:
        raise ValueError("Warm-ups cannot be negative.")
    if samples < 7:
        raise ValueError("At least 7 measured samples are required.")
    sessions = []
    try:
        for session_index in range(2):
            sessions.append(
                _session(
                    config,
                    original,
                    candidate,
                    session_index=session_index,
                    warmups=warmups,
                    samples=samples,
                    timeout_seconds=timeout_seconds,
                    max_rows=max_rows,
                )
            )
    except QueryExecutionFailure as error:
        return {
            "sessions": sessions,
            "complete": False,
            "error_code": error.code,
            "warmup_count": warmups,
            "configured_samples_per_query_per_session": samples,
        }
    return {
        "sessions": sessions,
        "complete": True,
        "error_code": None,
        "warmup_count": warmups,
        "configured_samples_per_query_per_session": samples,
    }


def promotion_decision(equivalence, benchmark: dict, candidate) -> dict:
    checks = {
        "exact_output_equivalence": equivalence.equivalent,
        "no_timeout_or_error": benchmark.get("complete") is True,
        "two_sessions": len(benchmark.get("sessions", [])) == 2,
        "minimum_samples_each": False,
        "paired_win_rate_at_least_80_percent": False,
        "runtime_and_cost_available": False,
        "composite_improvement_greater_than_5_percent": False,
        "strict_machine_checkable_preconditions": candidate.strict_machine_preconditions,
        "no_hard_coded_identifiers": candidate.schema_agnostic_rule,
    }
    sessions = benchmark.get("sessions", [])
    if len(sessions) == 2:
        checks["minimum_samples_each"] = all(
            item["original"]["sample_count"] >= 7 and item["candidate"]["sample_count"] >= 7
            for item in sessions
        )
        checks["paired_win_rate_at_least_80_percent"] = all(
            item["paired_win_rate_percent"] >= 80.0 for item in sessions
        )
        checks["runtime_and_cost_available"] = all(
            item["median_improvement_percent"] is not None
            and item["cost_improvement_percent"] is not None
            for item in sessions
        )
        checks["composite_improvement_greater_than_5_percent"] = all(
            (item.get("composite_improvement_percent") or float("-inf")) > 5.0
            for item in sessions
        )

    if not equivalence.equivalent:
        status = "rejected"
    elif not benchmark.get("complete") or len(sessions) < 2:
        status = "insufficient evidence"
    elif all(checks.values()):
        status = "eligible for human rule review"
    else:
        status = "rejected"
    return {"status": status, "checks": checks}
