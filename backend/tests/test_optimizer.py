import unittest

from optimizer import optimize_sql


def columns(_table):
    return ["student_id", "name", "created_at"]


class OptimizerTests(unittest.TestCase):
    def test_select_star_expands_known_columns(self):
        result = optimize_sql("SELECT * FROM students;", columns)
        self.assertTrue(result.optimized_query.startswith("SELECT `student_id`, `name`, `created_at`"))
        self.assertTrue(any(hint["rule"] == "select-star" and hint["applied"] for hint in result.hints))

    def test_year_uses_half_open_range_for_datetime_safety(self):
        result = optimize_sql("SELECT id FROM students WHERE YEAR(created_at) = 2025")
        self.assertIn("created_at >= '2025-01-01'", result.optimized_query)
        self.assertIn("created_at < '2026-01-01'", result.optimized_query)

    def test_year_and_month_use_next_month_boundary(self):
        result = optimize_sql("SELECT id FROM students WHERE YEAR(created_at)=2025 AND MONTH(created_at)=5")
        self.assertIn("created_at >= '2025-05-01'", result.optimized_query)
        self.assertIn("created_at < '2025-06-01'", result.optimized_query)

    def test_in_subquery_is_suggestion_not_rewrite(self):
        query = "SELECT id FROM students WHERE department_id IN (SELECT department_id FROM departments WHERE active = 1)"
        result = optimize_sql(query)
        self.assertEqual(result.optimized_query, query)
        self.assertTrue(any(hint["rule"] == "in-subquery" and not hint["applied"] for hint in result.hints))

    def test_or_union_is_not_applied_because_duplicates_can_change(self):
        query = "SELECT id FROM students WHERE active = 1 OR department_id = 2"
        result = optimize_sql(query)
        self.assertNotIn("UNION", result.optimized_query)
        self.assertTrue(any(hint["rule"] == "or-predicate" for hint in result.hints))

