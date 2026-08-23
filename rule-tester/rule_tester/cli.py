"""Command-line entry point for the local rewrite evidence harness."""

import argparse
import json
import os
from pathlib import Path
import sys

from .benchmark import promotion_decision, run_benchmark
from .bootstrap import BACKEND_ROOT  # noqa: F401
from .candidates import RULES, CandidateError, build_candidate
from .config import ConfigurationError, IntegrationConfig
from .equivalence import compare_queries
from .mysql_runtime import (
    QueryExecutionFailure,
    connect,
    mysql_version,
    schema_index_fingerprint,
)
from .report import write_report
from security import validate_read_only_query


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Locally validate and benchmark SQL rewrite candidates without changing rules."
    )
    result.add_argument("--list-rules", action="store_true")
    result.add_argument("--rule", choices=sorted(RULES))
    result.add_argument("--original-file", type=Path)
    result.add_argument("--candidate-file", type=Path)
    result.add_argument(
        "--interactive",
        action="store_true",
        help="Paste SQL interactively; finish each query with a line containing only __END__.",
    )
    result.add_argument("--warmups", type=int, default=1)
    result.add_argument("--samples", type=int, default=7)
    result.add_argument("--timeout-seconds", type=int, default=10)
    result.add_argument("--max-rows", type=int, default=100000)
    return result


def _read_sql(path: Path | None, label: str, interactive: bool) -> str:
    if interactive:
        print("Paste " + label.lower() + " SQL, then enter __END__ on its own line:")
        lines = []
        for line in sys.stdin:
            if line.rstrip("\r\n") == "__END__":
                break
            lines.append(line)
        if not lines:
            raise ValueError(label + " SQL is required.")
        return "".join(lines)
    if path is None:
        raise ValueError(label + " SQL file is required.")
    if not path.is_file():
        raise ValueError(label + " SQL file was not found.")
    return path.read_text(encoding="utf-8")


def _print_rules() -> None:
    for rule_id, metadata in RULES.items():
        print(rule_id + ": " + metadata["classification"] + " - " + metadata["description"])


def _deletion_instructions() -> None:
    print("Temporary tester deletion command after review (do not run until ready):")
    print("  macOS/Linux: rm -rf rule-tester")
    print("  PowerShell: Remove-Item -Recurse -Force rule-tester")


def main(argv=None) -> int:
    arguments = parser().parse_args(argv)
    if arguments.list_rules:
        _print_rules()
        return 0
    if not arguments.rule:
        print("error: --rule is required", file=sys.stderr)
        return 2
    if arguments.samples < 7 or arguments.warmups < 0:
        print("error: use at least 7 samples and a non-negative warm-up count", file=sys.stderr)
        return 2
    if arguments.timeout_seconds < 1 or arguments.max_rows < 1:
        print("error: timeout and max rows must be positive", file=sys.stderr)
        return 2

    try:
        original = validate_read_only_query(
            _read_sql(arguments.original_file, "Original", arguments.interactive)
        )
        proposed = None
        if arguments.rule == "manual":
            proposed = validate_read_only_query(
                _read_sql(arguments.candidate_file, "Candidate", arguments.interactive)
            )
        config = IntegrationConfig.from_environment()

        with connect(config, timeout_seconds=arguments.timeout_seconds) as connection:
            candidate = build_candidate(
                connection,
                config.database,
                arguments.rule,
                original,
                proposed,
            )
            candidate_sql = validate_read_only_query(candidate.candidate_sql)
            equivalence = compare_queries(
                connection,
                original,
                candidate_sql,
                max_rows=arguments.max_rows,
            )
            version = mysql_version(connection)
            fingerprint = schema_index_fingerprint(connection, config.database)

        if equivalence.equivalent:
            benchmark = run_benchmark(
                config,
                original,
                candidate_sql,
                warmups=arguments.warmups,
                samples=arguments.samples,
                timeout_seconds=arguments.timeout_seconds,
                max_rows=arguments.max_rows,
            )
        else:
            benchmark = {
                "sessions": [],
                "complete": False,
                "error_code": "EQUIVALENCE_REJECTED",
            }
        decision = promotion_decision(equivalence, benchmark, candidate)
        report_path = write_report(
            candidate=candidate,
            equivalence=equivalence,
            benchmark=benchmark,
            decision=decision,
            mysql_version=version,
            fingerprint=fingerprint,
        )

        display = {
            "rule": {
                "id": candidate.rule_id,
                "classification": candidate.classification,
            },
            "equivalence": {
                "equivalent": equivalence.equivalent,
                "ordered": equivalence.ordered,
                "original_row_count": equivalence.original_row_count,
                "candidate_row_count": equivalence.candidate_row_count,
                "reason_code": equivalence.reason_code,
            },
            "benchmark": benchmark,
            "promotion_decision": decision,
            "report": os.path.relpath(report_path, Path.cwd()),
        }
        print(json.dumps(display, indent=2, sort_keys=True))
        _deletion_instructions()
        return 0 if decision["status"] == "eligible for human rule review" else 1
    except (ConfigurationError, CandidateError, QueryExecutionFailure, ValueError):
        print("error: the tester could not complete; review configuration, SQL files, and sanitized diagnostics", file=sys.stderr)
        _deletion_instructions()
        return 2
    except Exception:
        print("error: unexpected tester failure; no secret-bearing diagnostics were emitted", file=sys.stderr)
        _deletion_instructions()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
