"""JSON endpoints for SQL optimization and plan analysis."""

from flask import Blueprint, current_app, jsonify, request
from pymysql import MySQLError

from analyzer import analyze_query, calculate_metrics
from database import get_columns
from optimizer import optimize_sql
from security import QueryValidationError, validate_read_only_query

api = Blueprint("api", __name__, url_prefix="/api")


def _payload_query() -> str:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise QueryValidationError("A JSON request body is required.")
    return validate_read_only_query(payload.get("query"))


def _resolver(config):
    return lambda table: get_columns(config, table)


@api.get("/health")
def health():
    return jsonify({"status": "ok", "service": "sql-refine-api"})


@api.post("/optimize")
def optimize():
    query = _payload_query()
    result = optimize_sql(query, _resolver(current_app.config["OPTIMIZED_DB"]))
    return jsonify({
        "originalQuery": result.original_query,
        "optimizedQuery": result.optimized_query,
        "hints": result.hints,
    })


@api.post("/analyze")
def analyze():
    query = _payload_query()
    return jsonify(analyze_query(query, current_app.config["ORIGINAL_DB"]))


@api.post("/compare")
def compare():
    query = _payload_query()
    original = analyze_query(query, current_app.config["ORIGINAL_DB"])
    optimization = optimize_sql(query, _resolver(current_app.config["OPTIMIZED_DB"]))
    optimized = analyze_query(optimization.optimized_query, current_app.config["OPTIMIZED_DB"])
    return jsonify({
        "original": original,
        "optimized": optimized,
        "hints": optimization.hints,
        "metrics": calculate_metrics(original, optimized),
    })


@api.errorhandler(QueryValidationError)
def validation_error(error):
    return jsonify({"error": {"code": "INVALID_QUERY", "message": str(error)}}), 400


@api.errorhandler(MySQLError)
def database_error(error):
    current_app.logger.warning("Database request failed: %s", error)
    return jsonify({"error": {"code": "DATABASE_ERROR", "message": "MySQL could not analyze the query. Check the SQL and database connection."}}), 422


@api.errorhandler(Exception)
def unexpected_error(error):
    current_app.logger.exception("Unhandled API error")
    return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "The request could not be completed."}}), 500

