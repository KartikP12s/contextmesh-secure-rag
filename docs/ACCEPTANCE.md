# Acceptance and architecture contract

1. PostgreSQL pgvector performs actual cosine ranking. SQL joins and predicates enforce tenant, current version and group membership before LIMIT/ranking results reach the provider.
2. Server-configured identity determines tenant and groups; query parameters cannot override identity.
3. TXT, Markdown, PDF and DOCX ingestion validates size/type, extracts text, chunks, embeds and persists index status/error. Updates atomically replace current chunks and increment version.
4. A local open-source FastEmbed model is the standard semantic embedding adapter. A clearly labeled hash embedding mode supports offline deterministic tests; optional OpenAI embeddings and answers require environment credentials.
5. Three synthetic tenants and multiple roles/groups demonstrate upload, search, grounded answers, citations, permissions, downloads and version replacement.
6. A 300-query dataset includes allowed/denied, cross-tenant, stale and insufficient-context cases; metrics derive from real pgvector results and actual returned citations.
7. React dashboard connects to functional APIs. Docker, CI, unit/integration/security/browser tests and honest reports precede publication.
