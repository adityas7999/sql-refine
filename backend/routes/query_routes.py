"""Secure JSON API for connection, schema, and query analysis workflows."""

from flask import Blueprint, current_app, jsonify, request
from sqlglot import exp, parse_one

from analyzer import benchmark_pair, calculate_metrics, explain_json
from audit import audit
from connection_manager import parse_connection_settings
from errors import ValidationError
from optimizer import optimize_sql
from schema_introspection import inspect_schema, list_databases, table_columns
from security import validate_identifier, validate_read_only_query

api = Blueprint("api", __name__, url_prefix="/api")


def _json_payload() -> dict:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationError("A JSON request body is required.")
    return payload


def _session_id() -> str:
    return request.headers.get("X-Connection-Session", "").strip()


def _manager():
    return current_app.extensions["connection_manager"]


def _limiter():
    return current_app.extensions["limiter"]


@api.get("/health")
def health():
    return jsonify({"status": "ok", "service": "sql-refine-api"})


@api.get("/ready")
def ready():
    if not _manager().is_ready():
        return jsonify({"status": "not-ready"}), 503
    return jsonify({"status": "ready"})


@api.post("/connections/test")
def test_connection():
    settings = parse_connection_settings(_json_payload())
    try:
        result = _manager().test(settings)
        audit("connection.test", host=settings.host, port=settings.port, tls=settings.ssl_enabled)
        return jsonify({"connected": True, **result})
    except Exception:
        audit("connection.test", outcome="failure", host=settings.host, port=settings.port, tls=settings.ssl_enabled)
        raise


@api.post("/connection-sessions")
def create_connection_session():
    settings = parse_connection_settings(_json_payload())
    _manager().test(settings)
    session_id = _manager().create_session(settings)
    audit("connection.session.created", session_id=session_id, host=settings.host, port=settings.port, tls=settings.ssl_enabled)
    return jsonify({
        "sessionId": session_id,
        "connection": {
            "name": settings.name, "host": settings.host, "port": settings.port,
            "username": settings.username, "defaultDatabase": settings.default_database,
            "sslEnabled": settings.ssl_enabled,
        },
    }), 201


@api.delete("/connection-sessions/current")
def delete_connection_session():
    session_id = _session_id()
    _manager().delete_session(session_id)
    audit("connection.session.deleted", session_id=session_id)
    return "", 204


@api.get("/databases")
def databases():
    session_id = _session_id()
    with _manager().connect(session_id) as connection:
        items = list_databases(connection)
    audit("schema.databases.listed", session_id=session_id, count=len(items))
    return jsonify({"databases": items})


@api.get("/schema")
def schema():
    session_id = _session_id()
    database = validate_identifier(request.args.get("database"), "database name")
    with _manager().connect(session_id, database) as connection:
        result = inspect_schema(
            connection, database,
            max_tables=current_app.config["SCHEMA_MAX_TABLES"],
            max_columns=current_app.config["SCHEMA_MAX_COLUMNS"],
        )
    audit("schema.inspected", session_id=session_id, database=database, table_count=len(result["tables"]))
    return jsonify(result)


def _schema_context(connection, database: str, query: str):
    expression = parse_one(query, read="mysql")
    table_names = list(dict.fromkeys(table.name for table in expression.find_all(exp.Table) if table.name))
    if len(table_names) != 1:
        return None, None
    table_name = validate_identifier(table_names[0], "table name")
    columns = table_columns(connection, database, table_name)
    visible = [item for item in columns if "INVISIBLE" not in (item.get("extra") or "").upper()]
    by_name = {item["name"].lower(): item["dataType"] for item in visible}

    def resolve_columns(requested_table: str):
        return [item["name"] for item in visible] if requested_table.lower() == table_name.lower() else []

    def resolve_type(column_reference: str):
        return by_name.get(column_reference.split(".")[-1].strip("`").lower())

    return resolve_columns, resolve_type


@api.post("/analyze")
def analyze():
    payload = _json_payload()
    query = validate_read_only_query(payload.get("query"))
    database = validate_identifier(payload.get("database"), "database name")
    mode = str(payload.get("mode") or "plan").lower()
    if mode not in {"plan", "runtime"}:
        raise ValidationError("Analysis mode must be 'plan' or 'runtime'.", "INVALID_ANALYSIS_MODE")
    if mode == "runtime" and payload.get("confirmRuntime") is not True:
        raise ValidationError("Runtime benchmarking requires explicit confirmation.", "RUNTIME_CONFIRMATION_REQUIRED")

    session_id = _session_id()
    with _manager().connect(session_id, database) as connection:
        resolve_columns, resolve_type = _schema_context(connection, database, query)
        optimization = optimize_sql(query, resolve_columns, resolve_type)
        optimized_query = optimization.optimized_query if optimization.changed else None
        if mode == "plan":
            original = explain_json(connection, query)
            optimized = explain_json(connection, optimized_query) if optimized_query else None
        else:
            benchmark = benchmark_pair(
                connection, query, optimized_query,
                warmups=current_app.config["RUNTIME_WARMUPS"],
                samples=current_app.config["RUNTIME_SAMPLES"],
            )
            original = benchmark["original"]
            optimized = benchmark.get("optimized")

    result = {
        "database": database, "mode": mode, "original": original, "optimized": optimized,
        "proposedQuery": optimization.optimized_query if optimization.changed else None,
        "suggestions": optimization.suggestions,
        "metrics": calculate_metrics(original, optimized),
        "warnings": (["EXPLAIN ANALYZE executes the query. Measurements are samples, not guarantees."] if mode == "runtime" else []),
    }
    audit("query.analyzed", session_id=session_id, database=database, mode=mode, optimized=bool(optimized_query), suggestion_count=len(optimization.suggestions))
    return jsonify(result)

