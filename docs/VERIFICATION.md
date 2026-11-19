# Verification

Date: 2026-11-19 (America/New_York).

- Installed Python dependencies in an isolated Python 3.12 environment and locked them; npm dependency installation succeeded.
- `ruff check backend tests scripts` and `ruff format --check backend tests scripts`: passed.
- `pytest -q`: **5 passed, 0 failed**, against real PostgreSQL/pgvector, each using an isolated schema. Includes cross-tenant/group denial, provider-context inspection, permission revocation, version invalidation, PDF/DOCX/TXT/Markdown extraction and invalid/oversized files.
- `python scripts/evaluate.py`: **300 scenario assertions passed, 0 failed** with local FastEmbed BGE inference and PostgreSQL cosine retrieval. Recall@5 1.0; precision@5 0.2; MRR 1.0; access violations 0; citation correctness 1.0; stale violations 0. Raw metrics/queries: `evaluation.json`.
- `npm run build`: TypeScript and Vite build passed.
- `npm test`: **2 passed, 0 failed**.
- `pip-audit -r requirements.lock`: no known vulnerabilities found.
- `npm audit --audit-level=high`: zero vulnerabilities.
- `docker compose build`: API and frontend images built successfully.

## Container and browser verification

- `docker compose up -d --build --wait`: all services healthy.
- Repeated all 300 queries through the containerized API using actual HTTP; all 300 passed with the metrics above. Tenant summaries persisted in PostgreSQL.
- `npm run e2e`: **1 Chromium test passed**, verifying grounded search, a current citation, and a denied cross-tenant download. Screenshot saved in `docs/dashboard.png`.
- Initial browser test had an ambiguous selector because navigation and submit controls shared a label; scoped the test to the main content and reran successfully.
- Initial GitHub CI pending first publication.

## Issues found and corrected

An initial PostgreSQL test setup allowed schema lookup to fall back to public demo tables, which produced a misleading version mismatch. Tests now explicitly create their own tables in the temporary schema before app startup. The corrected isolated suite passes. This was test isolation, not an accepted stale-data behavior.

## Limits

FastEmbed's public model was downloaded and inference executed locally. Hosted OpenAI adapters were not called: to test, configure `OPENAI_API_KEY`, select the hosted provider, reindex documents and rerun search/answer checks; charges may apply. Shared demo authentication is not OIDC. Python static type checking is not configured; frontend TypeScript is checked. TestClient reports a dependency deprecation warning about its httpx transport; tests pass. The evaluation's unindexed-source cases test explicit source-filter abstention, not calibrated open-domain uncertainty.
