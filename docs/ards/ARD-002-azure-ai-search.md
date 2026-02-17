# ARD-002: Azure AI Search as the Vector and Full-Text Search Store

> **Status:** Accepted
> **Date:** 2026-02-13
> **Decision Makers:** Engineering Team

## Context

The pipeline produces chunked Markdown content with text embeddings (1536-dimensional vectors from `text-embedding-3-small`) and associated image URLs. These chunks need to be stored in a search index that supports:

1. **Vector search** — semantic similarity queries over chunk embeddings
2. **Full-text search** — keyword queries over chunk content
3. **Hybrid search** — combining vector and full-text for optimal retrieval
4. **Filterable metadata** — filter by `article_id`, `section_header`, `key_topics`
5. **Stored image references** — each chunk carries 0–N Blob Storage URLs to related images
6. **Agent integration** — the index will be queried by AI agents (Azure AI Foundry) for RAG-based Q&A, including agentic retrieval

## Decision

**Use Azure AI Search** as the combined vector and full-text search store.

The index (`kb-articles`) is created by application code at runtime with the following schema:

| Field | Type | Purpose |
|-------|------|---------|
| `id` | `Edm.String` (key) | Unique chunk identifier |
| `article_id` | `Edm.String` (filterable) | Source article folder name |
| `chunk_index` | `Edm.Int32` (sortable) | Ordering within article |
| `content` | `Edm.String` (searchable) | Chunk text with inline image descriptions |
| `content_vector` | `Collection(Edm.Single)` (1536d) | Text embedding |
| `image_urls` | `Collection(Edm.String)` | Blob Storage URLs to related images |
| `source_url` | `Edm.String` | Original article URL |
| `title` | `Edm.String` (searchable) | Article title |
| `section_header` | `Edm.String` (filterable) | Section heading |
| `key_topics` | `Collection(Edm.String)` (filterable) | Topic tags |

The index uses HNSW vector search with cosine similarity and includes semantic search (free tier) for re-ranking.

## Alternatives Considered

### Alternative 1: Azure Cosmos DB with Vector Search (Rejected)

Cosmos DB supports vector indexing via DiskANN and integrates with Azure AI Search as a data source.

- **Pros:** Combined operational + vector store; change feed for incremental indexing
- **Cons:** Overkill for a read-heavy search workload with batch ingestion; higher cost; no built-in full-text search ranking (BM25); requires AI Search anyway for hybrid queries. Two services instead of one.

### Alternative 2: Standalone Vector Database (e.g., Qdrant, Pinecone) (Rejected)

Use a dedicated vector database separate from the Azure ecosystem.

- **Pros:** Purpose-built for vector similarity; potentially lower latency for pure vector queries
- **Cons:** No native Azure managed identity integration; separate service to manage; no built-in full-text/hybrid search; no semantic re-ranking; limited filtering capabilities compared to AI Search; additional operational overhead

### Alternative 3: Azure PostgreSQL with pgvector (Rejected)

Use Azure Database for PostgreSQL Flexible Server with the pgvector extension.

- **Pros:** Familiar SQL interface; can store relational metadata alongside vectors
- **Cons:** No built-in semantic re-ranking; limited hybrid search capabilities; requires custom ranking logic; heavier infrastructure for a search-only workload; no native agentic retrieval support

## Consequences

### Positive

- **Native Azure integration** — managed identity authentication, Bicep-deployable, Application Insights telemetry
- **Hybrid search out of the box** — vector (HNSW/cosine), full-text (BM25), and semantic re-ranking in a single query
- **Filterable metadata** — `article_id`, `section_header`, and `key_topics` enable scoped queries without post-filtering
- **Image URL storage** — `Collection(Edm.String)` field stores 0–N Blob Storage URLs per chunk, giving agents direct access to related images
- **Agentic retrieval** — AI Search integrates directly with Azure AI Foundry agents for grounded Q&A with citations
- **Free tier available** — sufficient for development (3 indexes, 50 MB, vector + semantic search included)
- **Scalable upgrade path** — Free → Basic → Standard tiers with minimal configuration changes

### Negative

- **Index management in code** — the index schema is created/managed by application code (`fn-index`), not IaC. Schema changes require redeployment and reindexing
- **Free tier limits** — 50 MB storage, 3 indexes, no SLA. Production workloads require a paid tier
- **Push model** — the pipeline pushes documents to the index (vs. pull-based indexers). This is intentional for control but means no automatic incremental sync

## References

- [Architecture Spec — AI Search Index Schema](../specs/architecture.md)
- [Infrastructure Spec — Azure AI Search](../specs/infrastructure.md)
