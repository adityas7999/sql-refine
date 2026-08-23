import os

import pytest

from rule_tester.benchmark import run_benchmark
from rule_tester.config import ENVIRONMENT_KEYS, IntegrationConfig
from rule_tester.equivalence import compare_queries
from rule_tester.mysql_runtime import connect


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not all(os.environ.get(key) for key in ENVIRONMENT_KEYS),
    reason="MYSQL_INTEGRATION_* environment is not configured",
)
def test_exact_equivalence_and_two_session_protocol_against_mysql():
    config = IntegrationConfig.from_environment()
    with connect(config, timeout_seconds=10) as connection:
        evidence = compare_queries(
            connection,
            "SELECT 1 AS rule_tester_value",
            "SELECT 1 AS rule_tester_value",
            max_rows=10,
        )
    assert evidence.equivalent

    result = run_benchmark(
        config,
        "SELECT 1 AS rule_tester_value",
        "SELECT 1 AS rule_tester_value",
        warmups=1,
        samples=7,
        timeout_seconds=10,
        max_rows=10,
    )
    assert result["complete"]
    assert len(result["sessions"]) == 2
    assert all(session["original"]["sample_count"] == 7 for session in result["sessions"])
    assert all(session["candidate"]["sample_count"] == 7 for session in result["sessions"])
