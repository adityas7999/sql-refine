# SQLRefine

SQLRefine is a self-hosted MySQL query analysis and optimization tool built for teams that want safer, more explainable SQL review without exposing database credentials to the browser.

It gives you:

- a secure connection flow to MySQL through a backend-only session
- schema discovery and table inspection from real metadata
- plan-only analysis using `EXPLAIN FORMAT=JSON`
- optional runtime benchmarks with `EXPLAIN ANALYZE`
- conservative optimization suggestions that only apply when the rewrite is proven safe

```text
Browser UI → HTTPS/JSON → Flask security boundary → PyMySQL → authorized MySQL server
                     ├─ expiring credential session
                     ├─ SQLGlot AST validation
                     ├─ INFORMATION_SCHEMA discovery
                     ├─ EXPLAIN FORMAT=JSON (default)
                     └─ EXPLAIN ANALYZE (explicit benchmark only)
```

## Why teams use SQLRefine

- Query planning without execution by default
- Safer review of MySQL queries before production changes
- Better schema visibility without a direct DB client in the browser
- Conservative suggestions instead of risky automatic rewrites
- Clear separation between estimated plans and measured runtime

## Product at a glance

| Area | Details |
| --- | --- |
| Primary use | MySQL query inspection, analysis, and safe optimization review |
| Default mode | `EXPLAIN FORMAT=JSON` |
| Runtime mode | `EXPLAIN ANALYZE` with explicit confirmation |
| Security model | Credentials stay in backend memory only |
| Data access | Read-only MySQL account recommended |
| Optimization style | Narrow, schema-verified rewrites only |
| Frontend | React + Vite |
| Backend | Flask + PyMySQL + SQLGlot |

## Key metrics and defaults

These values define the product’s operational guardrails:

| Setting | Default | Purpose |
| --- | ---: | --- |
| `CONNECTION_SESSION_TTL_SECONDS` | `1800` | Session lifetime for backend-held credentials |
| `MAX_CONNECTION_SESSIONS` | `100` | In-memory connection session cap |
| `DB_CONNECT_TIMEOUT_SECONDS` | `5` | MySQL connect timeout |
| `DB_READ_TIMEOUT_SECONDS` | `30` | MySQL read timeout |
| `DB_WRITE_TIMEOUT_SECONDS` | `10` | MySQL write timeout |
| `STATEMENT_TIMEOUT_MS` | `10000` | MySQL `MAX_EXECUTION_TIME` per query |
| `RUNTIME_WARMUPS` | `1` | Unrecorded benchmark warm-ups |
| `RUNTIME_SAMPLES` | `3` | Recorded benchmark samples |
| `SCHEMA_MAX_TABLES` | `500` | Schema response limit |
| `SCHEMA_MAX_COLUMNS` | `10000` | Column discovery limit |
| `RATELIMIT_DEFAULT` | `120 per minute` | Default per-client request limit |

## Requirements

- Python 3.12 recommended
- Node.js 22 recommended
- MySQL 8.0.18+ for `EXPLAIN ANALYZE`; JSON plans work on earlier supported MySQL 8 releases
- Docker Compose v2 for container deployment

## Quick start

### One-command startup

From the project root, run:

```bash
python start.py
```

On Windows PowerShell:

```powershell
python .\start.py
```

This single command will:

- create a local `.env` file if needed
- create the backend virtual environment if missing
- install backend dependencies and frontend dependencies
- start the Flask API at `http://127.0.0.1:5000`
- start the Vite app at `http://localhost:4173`
- open the app in your default browser

If you prefer the Node wrapper:

```bash
npm start
```

### Manual startup

Copy the example configuration:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Start the backend in one terminal:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Start the frontend in another terminal:

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 4173
```

Then open:

- `http://localhost:4173`

The frontend proxies `/api` to the backend at `http://127.0.0.1:5000`.

## How to use SQLRefine

1. Connect to a MySQL instance using the connection form.
2. Test the connection without saving credentials.
3. Select a database from the discovered list.
4. Explore tables and columns from real schema metadata.
5. Paste a SQL statement to analyze.
6. Choose one of the analysis modes:
   - `plan`: safe, non-executing plan review
   - `runtime`: benchmark with explicit confirmation
7. Review the output and optimization hints.
8. Apply any proposed rewrites only after validating business and data semantics.

## Supported analysis modes

### 1) Plan-only mode (default)

Uses `EXPLAIN FORMAT=JSON`.

This mode is designed to understand:

- access paths
- rows estimated by the optimizer
- table scan vs index usage
- cost signals from MySQL

It does not execute the query, which makes it suitable for early review and safe investigation.

### 2) Runtime benchmark mode

Uses `EXPLAIN ANALYZE`.

This mode executes the SQL and is intentionally gated behind explicit user confirmation. It is useful for measuring real query cost, but it should be used carefully against production or sensitive workloads.

SQLRefine uses:

- alternating original/optimized order
- warm-up rounds
- multiple samples
- median timing and variance reporting

## Optimization safety model

SQLRefine is intentionally conservative. It only applies transformations that can be proven safe in the schema context.

### Safe automatic rewrites

- `SELECT *` expansion to explicit visible columns from a single table
- `YEAR(column) = 2025` to a half-open range when the column is verified as a temporal type
- `YEAR(column) = 2025 AND MONTH(column) = 12` to an equivalent half-open date range when the type is verified

### Suggestions only (not auto-applied)

These remain warnings or recommendations because they may change duplicates, ordering, NULL behavior, row counts, or expression semantics:

- `OR` to `UNION ALL`
- removing `DISTINCT`
- `IN` to `EXISTS` without additional verification
- removing case-conversion functions
- inventing a `LIMIT`
- substring, rounding, or collation-dependent rewrites

## Security and deployment guidance

SQLRefine is designed to keep database credentials out of the browser.

### Security model

- MySQL credentials are held in the backend only, in expiring process memory
- the frontend stores only an opaque session identifier
- credentials are never persisted in `localStorage`, `sessionStorage`, cookies, URLs, or Git
- database access is restricted through a dedicated read-only MySQL account
- query validation rejects comments, DDL/DML, file access, procedure calls, and unsafe functions

### Production guidance

- use a dedicated MySQL account with `SELECT` only
- restrict the source IP or network origin of that account
- prefer HTTPS in front of the app
- leave `CORS_ORIGINS` empty for the bundled same-origin frontend
- keep one backend worker if using in-memory sessions
- use Redis or shared storage for multi-instance rate limiting if scaling out
- never enable the disposable integration profile in production

## Create a read-only MySQL account

MySQL admin steps:

```sql
CREATE USER 'sqlrefine_reader'@'sqlrefine-host.example' IDENTIFIED BY '<strong-random-secret>' REQUIRE SSL;
GRANT SELECT ON `your_database`.* TO 'sqlrefine_reader'@'sqlrefine-host.example';
FLUSH PRIVILEGES;
SHOW GRANTS FOR 'sqlrefine_reader'@'sqlrefine-host.example';
```

Recommended rules:

- do not grant `FILE`, `PROCESS`, `SUPER`, `EXECUTE`, DDL, or DML
- prefer a replica or staging database whenever possible
- restrict network access to trusted sources
- prefer TLS and certificate verification in production

## TLS and certificate handling

Enable TLS in the connection form if your MySQL deployment requires it.

Set `MYSQL_SSL_CA` to a CA bundle path when using a private CA. Leave certificate verification enabled in production. Disabling verification encrypts traffic but does not validate the server identity.

## Docker deployment

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:8080` for the containerized frontend. In real deployments, publish through a reverse proxy with HTTPS and configure the backend to reach a MySQL hostname that is routable from the backend container.

Optional demo MySQL service:

```bash
export MYSQL_DEMO_ROOT_PASSWORD='<temporary-random-root-secret>'
export MYSQL_DEMO_PASSWORD='<temporary-random-reader-secret>'
docker compose --profile integration up --build
```

Windows PowerShell:

```powershell
$env:MYSQL_DEMO_ROOT_PASSWORD = '...'
$env:MYSQL_DEMO_PASSWORD = '...'
```

## API overview

Common endpoints:

- `GET /api/health`
- `GET /api/ready`
- `POST /api/connections/test`
- `POST /api/connection-sessions`
- `DELETE /api/connection-sessions/current`
- `GET /api/databases`
- `GET /api/schema?database=...`
- `POST /api/analyze`

Authenticated requests require the `X-Connection-Session` header.

## Testing

```bash
cd backend
pytest -q

cd ../frontend
npm install
npm run build
```

## Troubleshooting

- `cryptography package is required`: reinstall pinned backend dependencies
- connection refused: check routing from the backend host, not the browser
- access denied: verify user privileges, host restrictions, TLS policy, and password
- certificate failure: validate the CA bundle and backend configuration
- query timeout: reduce scope or analyze in plan-only mode first
- session expired: reconnect and resubmit the connection session
- no optimization: the rewrite could not be proven safe; suggestions may still appear

## Current limitations

- the in-memory credential store requires a single backend worker and expires on restart
- schema discovery is capped and loaded per database rather than paginated
- runtime benchmarks are workload-sensitive and should not replace production observability or controlled load testing
- SQLGlot enforces a strong parse boundary, but database privileges and isolation remain critical

## Summary

SQLRefine is meant for teams that want safer MySQL query analysis and conservative optimization guidance without making the browser a privileged database client. It favors correctness, explainability, and safe defaults over aggressive rewriting.
