"""Two-session alternating benchmark protocol and promotion decision."""

import math
import statistics
import time

from .mysql_runtime import QueryExecutionFailure, connect, execute_complete, explain_cost


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
    return {
        "session": session_index + 1,
        "raw_samples_ms": collected,
        "original": original_stats,
        "candidate": candidate_stats,
        "paired_win_rate_percent": wins / samples * 100.0,
        "median_improvement_percent": improvement_percent(
            original_stats["median_ms"], candidate_stats["median_ms"]
        ),
        "estimated_cost": costs,
        "cost_improvement_percent": improvement_percent(costs["original"], costs["candidate"]),
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
        "median_improvement_at_least_15_percent": False,
        "estimated_cost_improvement_at_least_10_percent_when_available": False,
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
        checks["median_improvement_at_least_15_percent"] = all(
            (item["median_improvement_percent"] or float("-inf")) >= 15.0 for item in sessions
        )
        cost_checks = []
        for item in sessions:
            original_cost = item["estimated_cost"]["original"]
            candidate_cost = item["estimated_cost"]["candidate"]
            if original_cost is None and candidate_cost is None:
                continue
            cost_checks.append(
                original_cost is not None
                and candidate_cost is not None
                and (item["cost_improvement_percent"] or float("-inf")) >= 10.0
            )
        checks["estimated_cost_improvement_at_least_10_percent_when_available"] = all(cost_checks)

    if not equivalence.equivalent:
        status = "rejected"
    elif not benchmark.get("complete") or len(sessions) < 2:
        status = "insufficient evidence"
    elif all(checks.values()):
        status = "eligible for human rule review"
    else:
        status = "rejected"
    return {"status": status, "checks": checks}
