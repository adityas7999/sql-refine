import unittest

from security import QueryValidationError, validate_read_only_query


class SecurityTests(unittest.TestCase):
    def test_rejects_unsafe_sql(self):
        queries = [
            "DROP TABLE students", "DELETE FROM students", "UPDATE students SET active=0",
            "INSERT INTO students VALUES (1)", "SELECT 1; DROP TABLE students",
            "WITH removed AS (DELETE FROM students RETURNING *) SELECT * FROM removed",
        ]
        for query in queries:
            with self.subTest(query=query), self.assertRaises(QueryValidationError):
                validate_read_only_query(query)

    def test_accepts_select_and_ignores_keywords_inside_literals(self):
        self.assertEqual(validate_read_only_query("SELECT 'drop table' AS example;"), "SELECT 'drop table' AS example")

