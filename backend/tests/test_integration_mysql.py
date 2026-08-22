import os

import pymysql
import pytest

from analyzer import explain_json
from security import validate_read_only_query

pytestmark = pytest.mark.integration


@pytest.mark.skipif(not os.getenv("MYSQL_INTEGRATION_HOST"), reason="Set MYSQL_INTEGRATION_HOST to run MySQL 8 integration tests")
def test_plan_only_against_disposable_mysql():
    connection = pymysql.connect(
        host=os.environ["MYSQL_INTEGRATION_HOST"], port=int(os.getenv("MYSQL_INTEGRATION_PORT", "3306")),
        user=os.getenv("MYSQL_INTEGRATION_USER", "sqlrefine"), password=os.getenv("MYSQL_INTEGRATION_PASSWORD", "sqlrefine"),
        database=os.getenv("MYSQL_INTEGRATION_DATABASE", "sqlrefine_demo"), autocommit=True,
    )
    try:
        plan = explain_json(connection, validate_read_only_query("SELECT 1"))
        assert plan["mode"] == "plan"
    finally:
        connection.close()

