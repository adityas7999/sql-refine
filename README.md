# SQLRefine

**Rule-Based SQL Query Optimization and Performance Analysis System**

SQLRefine is a DBMS teaching project that applies conservative SQL rewrite rules, runs MySQL `EXPLAIN ANALYZE`, and compares the original and optimized plans. Rewrites are applied only when the implementation can preserve meaning; risky ideas are shown as suggestions.

```text
React frontend
      ↓ REST/JSON
Flask API
      ↓
SQL rule engine
      ↓
MySQL → EXPLAIN ANALYZE
      ↓
Performance comparison
```

## Project structure

```text
backend/
  app.py             Flask application factory
  config.py          environment-backed configuration
  database.py        PyMySQL connection helpers
  optimizer.py       rule-based transformations and suggestions
  analyzer.py        EXPLAIN ANALYZE parser and metrics
  security.py        read-only SQL validation
  routes/             REST endpoints
  tests/              optimizer, analyzer, and security tests
frontend/
  src/components/     SQL workspace and result components
  src/services/api.js API client
```

## Prerequisites

- Python 3.10+
- Node.js 20.19+ or 22.12+
- MySQL 8.0.18+ (`EXPLAIN ANALYZE` support)

Use databases with equivalent schemas, data, indexes, and statistics for meaningful comparisons. Create a dedicated MySQL user with `SELECT` access only; never run this application with a privileged account.

## Configuration

Copy `.env.example` to `.env` and configure:

| Variable | Purpose |
| --- | --- |
| `DB_HOST`, `DB_PORT` | MySQL server |
| `DB_USER`, `DB_PASSWORD` | Read-only MySQL credentials |
| `ORIGINAL_DB_NAME` | Database used for the original query |
| `OPTIMIZED_DB_NAME` | Equivalent database used for the rewritten query |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |

The previous prototype contained a database password in source. That credential must be rotated; deleting it from the current file does not remove it from Git history.

## Run the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

The API runs at `http://127.0.0.1:5000`. Check `GET /api/health`.

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Vite runs at `http://localhost:5173` and proxies `/api` to Flask. Set `VITE_API_URL` only if the API is hosted elsewhere.

## REST API

- `GET /api/health` — service status
- `POST /api/optimize` — return a safe rewrite and optimizer insights
- `POST /api/analyze` — return a parsed execution plan
- `POST /api/compare` — run the complete original-versus-optimized workflow

Every POST accepts `{ "query": "SELECT ..." }`. The backend allows one `SELECT` statement or SELECT-based CTE and rejects destructive or administrative keywords. This validator is a conservative project guardrail, not a substitute for database privileges or process isolation.

## Optimizer behavior

Applied rewrites:

- simple `SELECT *` expansion using schema metadata
- `YEAR()` and combined `YEAR()`/`MONTH()` predicates to half-open ranges
- safe fixed-prefix `LEFT()`/`SUBSTR()` comparisons to prefix `LIKE`

Suggestions only:

- `IN` subqueries, `OR` predicates, and `DISTINCT` with `GROUP BY`
- unbounded `ORDER BY`, leading-wildcard searches, and non-sargable functions
- `COUNT(*)` when only existence may be needed, and joins lacking `ON`/`USING`

The suggestion-only distinction is important: `OR → UNION ALL`, unconditional `IN → EXISTS`, removing `DISTINCT`, or inventing a `LIMIT` can change query results.

## Metrics

For positive original values:

```text
improvement % = (original - optimized) / original × 100
composite score = time improvement × 0.6 + cost improvement × 0.4
```

Missing and zero denominators remain unavailable rather than being replaced with artificial values. Negative scores are displayed as regressions.

## Tests and build

```bash
cd backend && pytest
cd frontend && npm install && npm run build
```

## Limitations

- SQL rewrites intentionally support a conservative subset of MySQL syntax; an AST parser is the next step for broader coverage.
- `EXPLAIN ANALYZE` executes the query to measure it. Use a read-only user, test data, timeouts, and an isolated MySQL environment.
- Separate databases can make comparisons misleading when their data, caches, indexes, or statistics differ.
- Benchmark results are single observations; serious performance work should alternate order and report repeated-run distributions.

