import os

import pymysql
import pytest

from analyzer import explain_json
from security import validate_read_only_query

pytestmark = pytest.mark.integration

REQUIRED_INTEGRATION_VARIABLES = (
    "MYSQL_INTEGRATION_HOST",
    "MYSQL_INTEGRATION_PORT",
    "MYSQL_INTEGRATION_USER",
    "MYSQL_INTEGRATION_PASSWORD",
    "MYSQL_INTEGRATION_DATABASE",
)


def _integration_environment_is_complete() -> bool:
    return all(os.getenv(name) is not None for name in REQUIRED_INTEGRATION_VARIABLES)


@pytest.mark.skipif(
    not _integration_environment_is_complete(),
    reason="Set all MYSQL_INTEGRATION_* variables to run MySQL 8 integration tests",
)
def test_plan_only_against_disposable_mysql():
    connection = pymysql.connect(
        host=os.environ["MYSQL_INTEGRATION_HOST"],
        port=int(os.environ["MYSQL_INTEGRATION_PORT"]),
        user=os.environ["MYSQL_INTEGRATION_USER"],
        password=os.environ["MYSQL_INTEGRATION_PASSWORD"],
        database=os.environ["MYSQL_INTEGRATION_DATABASE"],
        autocommit=True,
    )
    try:
        plan = explain_json(connection, validate_read_only_query("SELECT 1"))
        assert plan["mode"] == "plan"
    finally:
        connection.close()
