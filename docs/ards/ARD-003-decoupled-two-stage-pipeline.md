# ARD-003: Decoupled Two-Stage Pipeline with Serving Layer

> **Status:** Accepted
> **Date:** 2026-02-13
> **Decision Makers:** Engineering Team

## Context

The system transforms source HTML knowledge base articles into searchable, AI-indexed content. This involves two fundamentally different concerns:

1. **Content transformation** — parsing HTML, extracting text via CU, analyzing images, merging results into clean Markdown
2. **Search indexing** — chunking Markdown, generating embeddings, pushing to Azure AI Search

These concerns have different input formats, different Azure service dependencies, different failure modes, and different change frequencies. A new source format (PDF, PowerPoint, audio) requires new transformation logic but identical indexing logic.

## Decision

**Split the pipeline into two independent Azure Functions (`fn-convert` and `fn-index`) decoupled by a serving layer (Azure Blob Storage).**

```
Staging (Blob) → fn-convert → Serving (Blob) → fn-index → AI Search
```

### Serving Layer Contract

The serving layer (`serving/` container) defines the contract between stages:

```
serving/{article-id}/
  ├── article.md        # Clean Markdown with inline image descriptions
  ├── summary.txt       # AI-generated article summary
  └── images/           # Original images renamed to .png
      ├── image1.png
      └── ...
```

`fn-index` only reads from this structure. It has no knowledge of the source format (HTML, PDF, etc.) or the transformation steps that produced the Markdown.

### Stage Responsibilities

| Stage | Input | Output | Azure Dependencies |
|-------|-------|--------|--------------------|
| `fn-convert` | Staging blob (HTML + images) | Serving blob (Markdown + PNGs) | Content Understanding, Storage |
| `fn-index` | Serving blob (Markdown + PNGs) | AI Search index | AI Foundry (embeddings), AI Search, Storage |

Both functions are manually triggered via HTTP. Each processes all articles in its respective source container.

## Alternatives Considered

### Alternative 1: Single Monolithic Function (Rejected)

One function that reads HTML, converts, chunks, embeds, and indexes in a single invocation.

- **Pros:** Simpler deployment; no intermediate storage layer
- **Cons:** Tight coupling between transformation and indexing logic; re-indexing requires re-converting; no reusable intermediate format; harder to test independently; longer execution time per invocation; new source formats require modifying the entire pipeline

### Alternative 2: Event-Driven Pipeline with Blob Triggers (Deferred)

Use Blob Storage triggers or Event Grid subscriptions to automatically invoke `fn-index` when `fn-convert` writes to the serving layer.

- **Pros:** Fully automated; no manual orchestration
- **Cons:** Adds complexity for the current scope (batch processing of a small number of articles); blob triggers have known latency issues; ordering and completion detection are non-trivial. Can be added later without changing the architecture.

### Alternative 3: Azure Durable Functions Orchestration (Rejected)

Use Durable Functions to orchestrate convert → index as a workflow with fan-out/fan-in.

- **Pros:** Built-in retry, status tracking, orchestration
- **Cons:** Overhead for a two-step sequential pipeline; couples the stages in a single deployment; the serving layer already provides the decoupling benefit. Durable Functions are better suited for complex multi-step workflows with branching logic.

## Consequences

### Positive

- **Independent development and testing** — each function can be developed, tested, and deployed independently. Unit tests for HTML parsing don't require AI Search; embedding tests don't require Content Understanding
- **Re-indexing without re-converting** — if the index schema, chunking strategy, or embedding model changes, only `fn-index` runs. Source article re-processing is avoided
- **Source-format extensibility** — adding PDF or PowerPoint ingestion requires only a new `fn-convert` variant. `fn-index` is reusable unchanged because it reads Markdown, not HTML
- **Debuggable intermediate state** — the serving layer is inspectable. `article.md` can be reviewed before indexing to verify conversion quality
- **Independent scaling** — convert is CU-bound (N+1 API calls per article); index is embedding-bound (1 call per chunk). Different scaling profiles, different throttling strategies
- **Article ID traceability** — the folder name (`{article-id}`) is the key that threads through staging → serving → search index, enabling end-to-end traceability

### Negative

- **Additional storage cost** — the serving layer duplicates article content (Markdown + images). Minimal at current scale (KB-sized articles, PNG images 13–40 KB each)
- **Manual orchestration** — the user must run `fn-convert` then `fn-index` in sequence. Acceptable for the current batch-processing use case; automatable later via triggers or orchestration
- **Two deployments** — both functions are in the same Function App (same deployment unit), so this is not an operational burden in practice

## References

- [Architecture Spec — Pipeline Flow](../specs/architecture.md)
- [Architecture Spec — Blob Storage Layout](../specs/architecture.md)
- [Architecture Proposal — Option 1: HTML-Direct Pipeline](../research/004-architecture-proposal.md)
