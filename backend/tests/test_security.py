import pytest

from errors import ValidationError
from security import quote_identifier, validate_identifier, validate_read_only_query


@pytest.mark.parametrize("query", [
    "DROP TABLE users", "DELETE FROM users", "UPDATE users SET active=0",
    "INSERT INTO users VALUES (1)", "CALL maintenance()", "CREATE TABLE x(id INT)",
    "SELECT SLEEP(10)", "SELECT LOAD_FILE('/etc/passwd')", "SELECT * FROM users FOR UPDATE",
])
def test_dangerous_sql_is_rejected(query):
    with pytest.raises(ValidationError):
        validate_read_only_query(query)


@pytest.mark.parametrize("query", ["SELECT 1; SELECT 2", "SELECT 1; DROP TABLE users"])
def test_multiple_statements_are_rejected(query):
    with pytest.raises(ValidationError, match="Exactly one"):
        validate_read_only_query(query)


@pytest.mark.parametrize("query", ["SELECT 1 -- hidden", "SELECT /* injected */ 1", "SELECT 1 # hidden"])
def test_comments_are_rejected(query):
    with pytest.raises(ValidationError, match="comments"):
        validate_read_only_query(query)


def test_safe_cte_is_accepted():
    query = "WITH active_users AS (SELECT id FROM users WHERE active = 1) SELECT id FROM active_users"
    assert validate_read_only_query(query) == query


def test_mutating_cte_is_rejected():
    with pytest.raises(ValidationError):
        validate_read_only_query("WITH changed AS (UPDATE users SET active=0 RETURNING id) SELECT id FROM changed")


@pytest.mark.parametrize("value", ["", None, " x", "x ", "bad\x00name", "bad\nname", "x" * 65])
def test_invalid_identifiers_are_rejected(value):
    with pytest.raises(ValidationError):
        validate_identifier(value)


def test_identifier_is_quoted_after_validation():
    assert quote_identifier("customer-db") == "`customer-db`"
    assert quote_identifier("Customer data") == "`Customer data`"
    assert quote_identifier("odd`name") == "`odd``name`"
