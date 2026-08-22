"""Plan-only analysis and explicitly confirmed runtime benchmarking."""

import json
import re
import statistics
import time

from errors import DatabaseAccessError, ValidationError

TIME_WEIGHT = 0.6
COST_WEIGHT = 0.4


def _number(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def parse_json_plan(raw_plan: object) -> dict:
    try:
        document = json.loads(raw_plan) if isinstance(raw_plan, str) else raw_plan
    except (TypeError, json.JSONDecodeError) as error:
        raise DatabaseAccessError("MySQL returned an unreadable JSON execution plan.", "MALFORMED_PLAN") from error
    if not isinstance(document, dict):
        raise DatabaseAccessError("MySQL returned an unexpected execution-plan format.", "MALFORMED_PLAN")

    plan = []
    seen = set()

    def visit(node, depth=0, label=None):
        if isinstance(node, list):
            for child in node:
                visit(child, depth, label)
            return
        if not isinstance(node, dict):
            return
        marker = id(node)
        if marker in seen:
            return
        seen.add(marker)
        table_name = node.get("table_name")
        operation = node.get("access_type") or label
        cost_info = node.get("cost_info") if isinstance(node.get("cost_info"), dict) else {}
        if table_name or operation in {"grouping_operation", "ordering_operation", "duplicates_removal", "union_result"}:
            title = f"{operation or 'table'} on {table_name}" if table_name else str(operation).replace("_", " ")
            plan.append({
                "depth": depth, "operation": title,
                "cost": _number(cost_info.get("prefix_cost") or cost_info.get("query_cost")),
                "estimatedRows": _number(node.get("rows_produced_per_join") or node.get("rows_examined_per_scan")),
                "actualTime": None, "actualRows": None, "loops": None,
            })
            depth += 1
        for key, value in node.items():
            if isinstance(value, (dict, list)) and key not in {"cost_info", "used_columns", "attached_condition"}:
                visit(value, depth, key)

    visit(document)
    query_block = document.get("query_block", {}) if isinstance(document.get("query_block"), dict) else {}
    cost_info = query_block.get("cost_info", {}) if isinstance(query_block.get("cost_info"), dict) else {}
    return {"plan": plan, "estimatedCost": _number(cost_info.get("query_cost"))}


def parse_explain_analyze_rows(rows) -> dict:
    plan = []
    indexes = set()
    for row in rows:
        if not row or row[0] is None:
            continue
        line = str(row[0])
        leading = len(line) - len(line.lstrip())
        depth = max(0, leading // 4)
        cost_match = re.search(r"cost=([0-9.]+)(?:\.\.([0-9.]+))?\s+rows=([0-9.]+)", line)
        actual_match = re.search(r"actual time=([0-9.]+)\.\.([0-9.]+)\s+rows=([0-9.]+)\s+loops=([0-9.]+)", line)
        index_match = re.search(r"\b(?:index|using)\s+(?:lookup on |scan on )?`?([A-Za-z0-9_$]+)`?", line, re.IGNORECASE)
        if index_match:
            indexes.add(index_match.group(1))
        operation = re.sub(r"^\s*->\s*", "", line)
        operation = re.sub(r"\s*\((?:cost|actual time)=.*$", "", operation).strip()
        plan.append({
            "depth": depth, "operation": operation,
            "cost": _number(cost_match.group(2) or cost_match.group(1)) if cost_match else None,
            "estimatedRows": _number(cost_match.group(3)) if cost_match else None,
            "actualTime": f"{actual_match.group(1)}..{actual_match.group(2)}" if actual_match else None,
            "actualRows": _number(actual_match.group(3)) if actual_match else None,
            "loops": _number(actual_match.group(4)) if actual_match else None,
        })
    return {"plan": plan, "indexes": sorted(indexes)}


def explain_json(connection, query: str) -> dict:
    with connection.cursor() as cursor:
        cursor.execute("EXPLAIN FORMAT=JSON " + query)
        row = cursor.fetchone()
    if not row:
        raise DatabaseAccessError("MySQL returned no execution plan.", "EMPTY_PLAN")
    return {"query": query, "mode": "plan", **parse_json_plan(row[0]), "runtime": None}


def _run_analyze(connection, query: str) -> tuple[dict, float]:
    started = time.perf_counter()
    with connection.cursor() as cursor:
        cursor.execute("EXPLAIN ANALYZE " + query)
        rows = cursor.fetchall()
    elapsed_ms = (time.perf_counter() - started) * 1000
    return parse_explain_analyze_rows(rows), elapsed_ms


def benchmark_pair(connection, original_query: str, optimized_query: str | None, *, warmups: int, samples: int) -> dict:
    labels = ["original"] + (["optimized"] if optimized_query and optimized_query != original_query else [])
    queries = {"original": original_query, "optimized": optimized_query}
    collected = {label: [] for label in labels}
    final_plans = {}
    total_rounds = warmups + samples
    for round_index in range(total_rounds):
        order = labels if round_index % 2 == 0 else list(reversed(labels))
        for label in order:
            plan, elapsed_ms = _run_analyze(connection, queries[label])
            final_plans[label] = plan
            if round_index >= warmups:
                collected[label].append(elapsed_ms)
    result = {}
    for label in labels:
        values = collected[label]
        result[label] = {
            "query": queries[label], "mode": "runtime", **final_plans[label],
            "estimatedCost": next((row["cost"] for row in final_plans[label]["plan"] if row["cost"] is not None), None),
            "runtime": {
                "samplesMs": [round(value, 4) for value in values],
                "medianMs": statistics.median(values),
                "varianceMs2": statistics.variance(values) if len(values) > 1 else 0.0,
                "sampleCount": len(values), "warmupCount": warmups,
            },
        }
    return result


def _improvement(original, optimized):
    if original is None or optimized is None or original <= 0:
        return None
    return ((original - optimized) / original) * 100


def calculate_metrics(original: dict, optimized: dict | None) -> dict:
    if not optimized:
        return {"timeEfficiency": None, "costEfficiency": None, "compositeScore": None}
    original_time = (original.get("runtime") or {}).get("medianMs")
    optimized_time = (optimized.get("runtime") or {}).get("medianMs")
    time_efficiency = _improvement(original_time, optimized_time)
    cost_efficiency = _improvement(original.get("estimatedCost"), optimized.get("estimatedCost"))
    composite = None
    if time_efficiency is not None and cost_efficiency is not None:
        composite = time_efficiency * TIME_WEIGHT + cost_efficiency * COST_WEIGHT
    return {"timeEfficiency": time_efficiency, "costEfficiency": cost_efficiency, "compositeScore": composite}

