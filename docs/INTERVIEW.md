# Interview preparation

**30 seconds:** ContextMesh is a multitenant document search application with real local neural embeddings and pgvector retrieval. It enforces tenant and group access in SQL before sending context to the answer provider. Users can upload, replace, secure and search documents and inspect actual chunk citations. A 300-query synthetic evaluation tests retrieval, tenant/group denial, stale versions and citation provenance.

**Two minutes:** Upload a policy into the HR group, then ask a natural-language question. FastAPI derives identity from server configuration, extracts/chunks the file and runs a local BGE embedding model. PostgreSQL stores vectors and metadata. Search joins chunks to documents and applies tenant, group, current-version and provider predicates before returning nearest neighbors. The extractive answer provider quotes only these sources, and citation views reauthorize access. Switch to another tenant and show the document download is denied. Replace the policy, rerun the query and demonstrate that superseded chunk IDs stop resolving. Finish with the evaluation report: perfect synthetic recall does not mean perfect retrieval precision or production quality.

**Hardest decision:** Making permission filtering part of retrieval rather than retrieving globally and redacting afterward. Global retrieval can expose data to models/logs even if the UI hides it. A shared SQL predicate reduces that failure mode across search, listing, download and citation routes.

**Reliability/security:** Atomic version/chunk replacement, explicit failed indexing status, strict schema boundaries, bounded parsing and embedding-provider separation. Development tokens are documented as a limitation; production identity and ingestion queues remain future work.

1. **Why filter before top-K?** It prevents unauthorized context exposure and ensures authorized documents can fill the candidate set rather than being lost when denied results are removed afterward.
2. **What happens to citations after an update?** The old chunks are removed and their IDs return 404. New chunks carry the incremented document version. Failed reindexing excludes the document instead of silently serving old content.
3. **What does 100% recall mean here?** The relevant source appears in the top five for each positive synthetic query. With one labeled relevant document and five results, precision is 20%; the small corpus is not evidence of general enterprise accuracy.
