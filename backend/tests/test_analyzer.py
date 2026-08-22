import unittest

from analyzer import calculate_metrics, parse_explain_rows


class AnalyzerTests(unittest.TestCase):
    def test_parser_tolerates_partial_plan_lines(self):
        parsed = parse_explain_rows([
            ("-> Sort: students.name  (cost=12.50 rows=10) (actual time=0.100..0.250 rows=10 loops=1)",),
            ("    -> Table scan on students",),
            (None,),
        ])
        self.assertEqual(parsed["totalTimeMs"], 0.25)
        self.assertEqual(parsed["plannerCost"], 12.5)
        self.assertIsNone(parsed["plan"][1]["cost"])

    def test_metrics_keep_missing_values_null_and_allow_regression(self):
        unavailable = calculate_metrics({"totalTimeMs": 0, "plannerCost": None}, {"totalTimeMs": 1, "plannerCost": 2})
        self.assertEqual(unavailable, {"timeEfficiency": None, "costEfficiency": None, "compositeScore": None})
        regression = calculate_metrics({"totalTimeMs": 10, "plannerCost": 10}, {"totalTimeMs": 15, "plannerCost": 20})
        self.assertLess(regression["compositeScore"], 0)

