"""MySQL EXPLAIN ANALYZE execution and tolerant text-plan parsing."""

import re

TIME_WEIGHT = 0.6
COST_WEIGHT = 0.4


def parse_explain_rows(rows) -> dict:
    plan = []
    total_time = None
    planner_cost = None
    indexes = set()
    for row in rows:
        if not row or row[0] is None:
            continue
        line = str(row[0])
        leading = len(line) - len(line.lstrip())
        depth = max(0, leading // 4)
        cost_match = re.search(r"cost=([0-9]+(?:\.[0-9]+)?)(?:\.\.([0-9]+(?:\.[0-9]+)?))?\s+rows=([0-9]+(?:\.[0-9]+)?)", line)
        actual_match = re.search(r"actual time=([0-9]+(?:\.[0-9]+)?)\.\.([0-9]+(?:\.[0-9]+)?)\s+rows=([0-9]+(?:\.[0-9]+)?)\s+loops=([0-9]+(?:\.[0-9]+)?)", line)
        index_match = re.search(r"\b(?:index|using)\s+(?:lookup on |scan on )?`?([A-Za-z0-9_$]+)`?", line, re.IGNORECASE)
        cost = float(cost_match.group(2) or cost_match.group(1)) if cost_match else None
        estimated_rows = float(cost_match.group(3)) if cost_match else None
        actual_start = float(actual_match.group(1)) if actual_match else None
        actual_end = float(actual_match.group(2)) if actual_match else None
        actual_rows = float(actual_match.group(3)) if actual_match else None
        loops = float(actual_match.group(4)) if actual_match else None
        if planner_cost is None and cost is not None:
            planner_cost = cost
        if total_time is None and actual_end is not None:
            total_time = actual_end
        if index_match:
            indexes.add(index_match.group(1))
        operation = re.sub(r"^\s*->\s*", "", line)
        operation = re.sub(r"\s*\((?:cost|actual time)=.*$", "", operation).strip()
        plan.append({
            "depth": depth, "operation": operation, "cost": cost,
            "estimatedRows": estimated_rows,
            "actualTime": None if actual_start is None else f"{actual_start}..{actual_end}",
            "actualRows": actual_rows, "loops": loops,
        })
    return {"plan": plan, "totalTimeMs": total_time, "plannerCost": planner_cost, "indexes": sorted(indexes)}


def analyze_query(query: str, database_config: dict) -> dict:
    from database import connection

    with connection(database_config, streaming=True) as db, db.cursor() as cursor:
        cursor.execute("EXPLAIN ANALYZE " + query)
        return {"query": query, **parse_explain_rows(cursor.fetchall())}


def _improvement(original, optimized):
    if original is None or optimized is None or original <= 0:
        return None
    return ((original - optimized) / original) * 100


def calculate_metrics(original: dict, optimized: dict) -> dict:
    time_efficiency = _improvement(original.get("totalTimeMs"), optimized.get("totalTimeMs"))
    cost_efficiency = _improvement(original.get("plannerCost"), optimized.get("plannerCost"))
    composite = None
    if time_efficiency is not None and cost_efficiency is not None:
        composite = time_efficiency * TIME_WEIGHT + cost_efficiency * COST_WEIGHT
    return {"timeEfficiency": time_efficiency, "costEfficiency": cost_efficiency, "compositeScore": composite}
