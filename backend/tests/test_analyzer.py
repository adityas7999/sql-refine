import json

from analyzer import calculate_metrics, parse_explain_analyze_rows, parse_json_plan


def test_json_plan_parses_estimates_without_runtime_values():
    raw = json.dumps({"query_block": {"cost_info": {"query_cost": "12.4"}, "table": {"table_name": "orders", "access_type": "range", "rows_examined_per_scan": 5, "cost_info": {"prefix_cost": "12.4"}}}})
    parsed = parse_json_plan(raw)
    assert parsed["estimatedCost"] == 12.4
    assert parsed["plan"][0]["operation"] == "range on orders"
    assert parsed["plan"][0]["actualTime"] is None


def test_runtime_parser_tolerates_missing_fields():
    parsed = parse_explain_analyze_rows([("-> Table scan on orders",), (None,)])
    assert parsed["plan"][0]["cost"] is None
    assert parsed["plan"][0]["actualRows"] is None


def test_metrics_distinguish_missing_time_and_negative_regression():
    plan_only = calculate_metrics({"estimatedCost": 10, "runtime": None}, {"estimatedCost": 8, "runtime": None})
    assert plan_only["timeEfficiency"] is None
    assert plan_only["costEfficiency"] == 20
    assert plan_only["compositeScore"] is None
    regression = calculate_metrics(
        {"estimatedCost": 10, "runtime": {"medianMs": 10}},
        {"estimatedCost": 20, "runtime": {"medianMs": 15}},
    )
    assert regression["compositeScore"] < 0

