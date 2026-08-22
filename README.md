# SQLRefine

**Secure, self-hosted MySQL query planning, schema exploration, and conservative optimization.**

SQLRefine lets an authorized user connect through a Flask backend to any compatible MySQL server, inspect accessible schemas, generate non-executing JSON plans by default, and optionally run explicitly confirmed benchmarks. The browser never connects directly to MySQL.

```text
React/Vite → HTTPS/JSON → Flask security boundary → PyMySQL → authorized MySQL server
                            ├─ expiring credential session
                            ├─ SQLGlot MySQL AST policy
                            ├─ INFORMATION_SCHEMA discovery
                            ├─ EXPLAIN FORMAT=JSON (default)
                            └─ EXPLAIN ANALYZE (explicit benchmark only)
```

## Security model

- MySQL credentials are submitted to the self-hosted backend, held only in expiring process memory, and never returned. React clears the password after creating a session and stores only an opaque session ID in component memory—not `localStorage`, `sessionStorage`, cookies, URLs, or Git.
- SQLGlot parses the query with the MySQL dialect. SQLRefine accepts exactly one top-level SELECT/SELECT CTE, rejects comments, mutation/DDL/admin AST nodes, locking, file access, procedure calls, and dangerous functions such as `SLEEP`, `BENCHMARK`, and `LOAD_FILE`.
- Metadata queries use parameters against `INFORMATION_SCHEMA`; database and table identifiers are separately validated.
- Connections have connect/read/write limits, every session receives `MAX_EXECUTION_TIME`, request bodies are capped, endpoints are rate-limited, CORS is allowlisted, errors are sanitized, and audit events omit SQL and secrets.
- SQLRefine does not use cookie authentication, so CSRF tokens are not applicable to this design. The opaque connection-session ID is sent in a custom header and never persisted by the supplied frontend.

These controls are defense in depth. **Always create a dedicated MySQL account with `SELECT` only, restrict its network origin, and deploy SQLRefine behind HTTPS.** `EXPLAIN ANALYZE` executes the query and can still consume resources despite a read-only account.

The default credential store is intentionally ephemeral. Restarting the backend expires all sessions. Run one Gunicorn worker; multiple processes do not share sessions. For horizontal scaling, implement the same session-store interface using encrypted shared storage and a server-side key.

## Features

- Test a connection without saving it.
- Optional TLS with certificate validation; CA trust is configured on the backend.
- Discover databases available to the connected MySQL account.
- Search tables and columns; inspect types, primary keys, indexes, and foreign-key relationships.
- Generate a query from an actual discovered table—no assumed schema or sample table.
- Default plan-only analysis with `EXPLAIN FORMAT=JSON`.
- Explicit runtime mode with alternating original/optimized order, warm-ups, multiple samples, median, and variance.
- Safety-classified optimization insights. Only verified simple rewrites are applied; context-dependent or unsafe transformations remain warnings.

## Requirements

- Python 3.12 recommended
- Node.js 22 recommended
- MySQL 8.0.18+ for runtime `EXPLAIN ANALYZE`; JSON plans work on earlier supported MySQL 8 releases
- Docker Compose v2 for container deployment

## Local installation

Copy configuration:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Frontend, in a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://127.0.0.1:5000`.

## Create a read-only MySQL account

Run as a MySQL administrator and replace the example host, user, password, and database:

```sql
CREATE USER 'sqlrefine_reader'@'10.%' IDENTIFIED BY 'use-a-long-random-password' REQUIRE SSL;
GRANT SELECT ON `your_database`.* TO 'sqlrefine_reader'@'10.%';
FLUSH PRIVILEGES;
SHOW GRANTS FOR 'sqlrefine_reader'@'10.%';
```

Do not grant `FILE`, `PROCESS`, `SUPER`, `EXECUTE`, DDL, or DML privileges. Prefer a staging/read-replica endpoint and network allowlists. A user with access to several databases will see each one in the selector.

## TLS

Enable TLS in the connection form. Set `MYSQL_SSL_CA` to a CA bundle path mounted into the backend when using a private CA. Leave certificate verification enabled in production. Disabling verification encrypts traffic but does not authenticate the server and is vulnerable to interception.

## Analysis modes

### Plan only — default

Uses `EXPLAIN FORMAT=JSON`. MySQL produces estimates without executing the SELECT. The UI displays estimated access operations, rows, and optimizer cost. Estimated cost is not elapsed time.

### Runtime benchmark — explicit confirmation

Uses `EXPLAIN ANALYZE`, which executes the SELECT. SQLRefine alternates original-first and optimized-first rounds, runs configurable warm-ups, and reports individual samples, median wall-clock time, and variance. Timeouts reduce risk but cannot guarantee zero impact. Never benchmark untrusted queries against a production primary.

## Optimizer safety

SQLRefine may apply only narrow, schema-verified rewrites:

- simple `SELECT * FROM one_table` expansion using visible columns;
- `YEAR()` or combined `YEAR()`/`MONTH()` to half-open ranges after confirming a temporal column type.

The following remain suggestions because they may change duplicates, NULL behavior, ordering, casing, or row counts:

- `OR` to `UNION ALL`;
- removing `DISTINCT`;
- unconditional `IN` to `EXISTS`;
- removing case-conversion functions;
- inventing a `LIMIT`;
- substring, rounding, or collation-dependent rewrites.

## Docker deployment

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:8080`. When MySQL runs on the Docker host, enter `host.docker.internal` as its host. For a remote MySQL server, enter its routable hostname.

An optional disposable MySQL 8 service is available for integration work:

```bash
docker compose --profile integration up --build
```

From SQLRefine, its hostname is `mysql-integration`, port `3306`, database `sqlrefine_demo`, user `sqlrefine`, and password from `MYSQL_DEMO_PASSWORD`. These defaults are for isolated local development only.

## Configuration

| Variable | Default | Purpose |
| --- | ---: | --- |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed browser origins |
| `CONNECTION_SESSION_TTL_SECONDS` | `1800` | Idle lifetime of server-side credentials |
| `MAX_CONNECTION_SESSIONS` | `100` | Maximum in-memory sessions |
| `DB_CONNECT_TIMEOUT_SECONDS` | `5` | MySQL connection timeout |
| `DB_READ_TIMEOUT_SECONDS` | `30` | Socket read timeout |
| `STATEMENT_TIMEOUT_MS` | `10000` | MySQL `MAX_EXECUTION_TIME` per SELECT |
| `RUNTIME_WARMUPS` | `1` | Unrecorded benchmark rounds |
| `RUNTIME_SAMPLES` | `3` | Recorded rounds, capped at 9 |
| `SCHEMA_MAX_TABLES` | `500` | Schema response table cap |
| `SCHEMA_MAX_COLUMNS` | `10000` | Schema response column cap |
| `MYSQL_SSL_CA` | empty | Backend path to a CA bundle |
| `RATELIMIT_STORAGE_URI` | `memory://` | Use Redis for multi-instance rate limits |

## API overview

- `GET /api/health` and `GET /api/ready`
- `POST /api/connections/test`
- `POST /api/connection-sessions`
- `DELETE /api/connection-sessions/current`
- `GET /api/databases`
- `GET /api/schema?database=...`
- `POST /api/analyze` with `mode: "plan"` or confirmed `mode: "runtime"`

Authenticated workflow calls require the opaque `X-Connection-Session` header. It is not a MySQL password and is never persisted by the supplied frontend.

## Tests

```bash
cd backend
pytest -q

cd ../frontend
npm ci
npm run build
```

To run the optional MySQL integration test, start the integration profile and set `MYSQL_INTEGRATION_HOST`, `MYSQL_INTEGRATION_PORT`, `MYSQL_INTEGRATION_USER`, `MYSQL_INTEGRATION_PASSWORD`, and `MYSQL_INTEGRATION_DATABASE` for the test process.

## Troubleshooting

- **`cryptography package is required`**: reinstall pinned backend requirements. `cryptography` is included.
- **Connection refused**: verify routing from the backend container/host, not from the browser. MySQL may be bound only to `127.0.0.1`.
- **Access denied**: inspect `SHOW GRANTS`, account host restrictions, password, database permission, and TLS requirements.
- **Certificate failure**: mount the correct CA bundle and set `MYSQL_SSL_CA`; do not disable verification in production.
- **Query timeout**: reduce query scope or review indexes using plan-only mode before increasing limits.
- **Session expired**: reconnect; credentials are deliberately not persisted.
- **No optimized comparison**: no rewrite could be proven semantics-preserving. Suggestions are still displayed.

## Remaining limitations

- The in-memory credential store requires one backend worker and loses sessions on restart.
- SQLGlot provides a strong parser boundary, but database privileges and isolation remain mandatory because parser defenses are not infallible.
- Schema discovery is capped and loaded per database rather than paginated.
- Benchmarks are workload-sensitive and not substitutes for production observability or controlled load testing.
