from schema_introspection import inspect_schema, list_databases


class SequenceCursor:
    def __init__(self, results): self.results = iter(results); self.current = []
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def execute(self, sql, params=None):
        assert "%s" in sql or sql.strip() == "SHOW DATABASES"
        self.current = next(self.results)
    def fetchall(self): return self.current


class FakeConnection:
    def __init__(self, results): self.results = results
    def cursor(self): return SequenceCursor(self.results)


def test_accessible_database_discovery():
    connection = FakeConnection(iter([[('app',), ('information_schema',)]]))
    assert list_databases(connection) == [{"name": "app", "system": False}, {"name": "information_schema", "system": True}]


def test_schema_introspection_groups_columns_indexes_and_relationships():
    results = iter([
        [("orders", "BASE TABLE", "InnoDB", 10, "")],
        [("orders", "id", 1, "bigint", "bigint", "NO", None, "PRI", "", ""), ("orders", "customer_id", 2, "bigint", "bigint", "NO", None, "MUL", "", "")],
        [("orders", "PRIMARY", 0, 1, "id", "A", 10, "BTREE")],
        [("orders", "customer_id", "fk_customer", "customers", "id")],
    ])
    schema = inspect_schema(FakeConnection(results), "shop")
    table = schema["tables"][0]
    assert table["columns"][0]["key"] == "PRI"
    assert table["indexes"][0]["name"] == "PRIMARY"
    assert table["relationships"][0]["referencedTable"] == "customers"

