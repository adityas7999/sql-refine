# SQL Refine local rule tester

This temporary, local-only CLI evaluates SQL rewrite evidence against a developer-controlled MySQL integration database. It imports the existing backend validator and optimizer rules without changing or enabling them. A successful outcome is only **eligible for human rule review**; the tool never edits or promotes a rule.

## Security boundaries

- Configure MySQL only through MYSQL_INTEGRATION_HOST, MYSQL_INTEGRATION_PORT, MYSQL_INTEGRATION_USER, MYSQL_INTEGRATION_PASSWORD, and MYSQL_INTEGRATION_DATABASE.
- Use a dedicated read-only MySQL account with access only to disposable integration data.
- Credentials remain in process memory. They are never printed, returned in reports, placed in SQL files, or saved by this tool.
- Do not put credentials in command arguments, query text, checked-in files, shell history, or local environment files inside the repository.
- SQL and result rows are not written to evidence reports. Reports contain only aggregate timings, estimated cost, rule metadata, row counts, equivalence outcome, MySQL version, a one-way schema/index fingerprint, and the decision.
- Complete result sets are compared up to the configured maximum. Reaching that maximum is truncation and can never pass equivalence.
- Queries execute against the configured database. The existing AST validator permits only one read-only SELECT or safe SELECT CTE, but queries can still be expensive. Keep the timeout bounded.
- The rule-test-results directory is ignored by Git by default. Review every sanitized report before explicitly choosing to commit it.

## Setup

Run these commands from the repository root.

macOS or Linux:

    cd rule-tester
    python3 -m venv .venv
    . .venv/bin/activate
    python -m pip install -r requirements.txt

Windows PowerShell:

    Set-Location rule-tester
    py -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt

Set the five required variables using your approved operating-system or secret-management mechanism. Example names only:

    MYSQL_INTEGRATION_HOST
    MYSQL_INTEGRATION_PORT
    MYSQL_INTEGRATION_USER
    MYSQL_INTEGRATION_PASSWORD
    MYSQL_INTEGRATION_DATABASE

The port has no implicit fallback: set it explicitly, normally to 3306. The CLI does not read a dotenv file.

## Commands

List the supported adapters:

    python -m rule_tester.cli --list-rules

Test the existing select-star rule from a SQL file outside the repository:

    python -m rule_tester.cli --rule select-star --original-file /safe/local/path/original.sql --warmups 1 --samples 7

Test the existing date-range rule:

    python -m rule_tester.cli --rule date-range --original-file /safe/local/path/original.sql --warmups 1 --samples 7

Compare a manually proposed rewrite:

    python -m rule_tester.cli --rule manual --original-file /safe/local/path/original.sql --candidate-file /safe/local/path/candidate.sql --warmups 1 --samples 7

Paste SQL without placing it in shell history:

    python -m rule_tester.cli --rule manual --interactive --warmups 1 --samples 7

For interactive input, paste the original SQL and enter __END__ on its own line. Then paste the candidate SQL and enter __END__ again.

The defaults are one warm-up, seven measured samples for each version in each of two sessions, a ten-second MySQL timeout, and a maximum of 100,000 rows. Increase the sample count if desired:

    python -m rule_tester.cli --rule select-star --original-file /safe/local/path/original.sql --warmups 2 --samples 15 --timeout-seconds 10 --max-rows 100000

Each pair alternates execution order, and session two starts with the opposite order. Standard output shows raw timing samples, median, mean, sample variance, p95, paired-win rate, estimated EXPLAIN JSON cost, every promotion check, and the final decision. It never shows SQL or result rows.

Manual candidates are intentionally unable to satisfy the rule-level machine-precondition and schema-agnostic checks. Their measurements are evidence for a developer to use when designing a conservative rule, not authorization to enable one.

## Tests

From the rule-tester directory:

    python -m pytest -q

When all five integration variables are present, the integration test runs exact equivalence plus the complete two-session, alternating seven-sample protocol against MySQL. Otherwise it is explicitly skipped:

    python -m pytest -q -m integration

## Evidence and cleanup

Completed evaluations write one redacted JSON report under the repository-root rule-test-results directory. Reports omit raw timing samples as well as SQL, result rows, credentials, database names, connection strings, table names, and column names.

After reviewing the evidence, delete only the temporary tester with the command appropriate for your shell. The tool prints these commands but never executes them.

macOS or Linux:

    rm -rf rule-tester

Windows PowerShell:

    Remove-Item -Recurse -Force rule-tester
