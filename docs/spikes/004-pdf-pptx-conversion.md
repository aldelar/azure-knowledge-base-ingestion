# Spike 004: PDF/PPTX Conversion Quality

> **Date:** 2026-03-20
> **Status:** Done ✅
> **Goal:** Validate that MarkItDown produces acceptable Markdown output from PDF and PPTX inputs, with focus on image extraction quality and PPTX speaker notes inclusion.

---

## Objective

Assess MarkItDown's viability for converting **PDF**, **PPTX**, and **DOCX** documents — the three formats planned for Epic 014 (Extended Data Sources). The current pipeline only handles HTML input. This spike de-risks Phase 1 by identifying conversion gaps before building 24 documents around the pipeline.

Key questions:
1. Does MarkItDown extract text, tables, and headings from PDF with acceptable fidelity?
2. Can embedded PDF images be extracted? If not, what alternative works best?
3. Does MarkItDown include PPTX speaker notes in its output?
4. Is DOCX conversion reliable (expected yes — MarkItDown uses `mammoth` internally)?

## Test Setup

- **MarkItDown version:** 0.1.5 with `[pdf,pptx,docx]` optional dependencies
- **PDF dependencies:** pdfminer-six 20251230, pypdfium2 5.6.0, pdfplumber 0.11.9
- **PPTX/DOCX dependencies:** python-pptx 1.0.2, python-docx 1.2.0
- **Image extraction:** PyMuPDF (fitz) 1.27.2.2
- **Sample docs:** Generated programmatically with reportlab (PDF), python-pptx (PPTX), python-docx (DOCX)

Sample documents include: headings, paragraphs, bullet points, tables (styled with headers), embedded PNG images, and (for PPTX) speaker notes on every slide.

## Results

### Conversion Quality Matrix

| Format | Chars | Lines | Headings | Links | Table Rows | Image Refs |
|--------|------:|------:|---------:|------:|-----------:|-----------:|
| PDF    | 2,091 |    38 |        0 |     0 |         12 |          0 |
| PPTX   | 2,135 |    47 |       10 |     2 |          6 |          2 |
| DOCX   |   894 |    32 |        4 |     0 |          7 |          1 |

### PDF Conversion Findings

| Aspect | Status | Details |
|--------|--------|---------|
| Paragraph text | ✅ | All paragraph content preserved accurately |
| Sub-headings | ✅ | Present as plain text (e.g., "System Architecture", "Component Overview") |
| Heading markers | ⚠️ | No `#` Markdown formatting — headings are plain text, not styled |
| Table (simple) | ✅ | API Endpoints table rendered correctly with pipes and alignment |
| Table (styled) | ⚠️ | Component Overview table partially broken — some rows lose pipe delimiters |
| Bullet points | ⚠️ | Rendered as `(cid:127)` — PDF character ID artifact instead of `•` or `-` |
| Image references | ❌ | MarkItDown produces **no** `![](...)` for embedded PDF images |
| Overall text fidelity | ✅ | All content words present and readable |

**PDF Image Extraction Comparison:**

| Approach | Images Found | Resolution | Format | Quality |
|----------|:----------:|-----------|--------|---------|
| MarkItDown native | 0 | N/A | N/A | No image extraction from PDF |
| PyMuPDF (fitz) | 2 | 400×250, 350×200 | PNG | ✅ Original resolution, lossless |

**Verdict:** MarkItDown extracts PDF text well but cannot extract embedded images. **PyMuPDF is required** for PDF image extraction — it extracts at original resolution with zero quality loss.

### PPTX Conversion Findings

| Aspect | Status | Details |
|--------|--------|---------|
| Slide titles | ✅ | All 5 slide titles extracted as `# Title` headings |
| Slide body text | ✅ | Bullet points and content preserved accurately |
| Speaker notes | ✅ | **All 5/5 speaker notes included** under `### Notes:` sections |
| Tables | ✅ | PPTX table rendered as pipe-delimited Markdown with headers |
| Image references | ✅ | `![name](PictureN.jpg)` — images referenced (generic filenames) |
| Slide structure | ✅ | `<!-- Slide number: N -->` comments mark slide boundaries |
| Formatting | ✅ | Text hierarchy (title → body → notes) preserved |

**Speaker Notes Verification:**

All 5 speaker notes keywords were found in MarkItDown output:
- ✅ "managed identity"
- ✅ "connection strings"
- ✅ "DefaultAzureCredential"
- ✅ "data flow"
- ✅ "cost-effective"

**python-pptx cross-validation:** 5/5 slides have notes (1,139 total chars). MarkItDown output matches.

**PPTX Image Extraction:**

| Approach | Images Found | Details |
|----------|:----------:|---------|
| MarkItDown (in Markdown) | 2 | Referenced as `![name](PictureN.jpg)` — generic names |
| python-pptx | 2 | Full blob access at original resolution |

**Verdict:** MarkItDown PPTX conversion is **excellent**. Speaker notes are included natively — no python-pptx supplementation needed. Images are referenced in the Markdown output.

### DOCX Conversion Findings (Spot Check)

| Aspect | Status | Details |
|--------|--------|---------|
| Headings | ✅ | 4 headings with `#` Markdown markers |
| Bullet lists | ✅ | Preserved with `*` markers |
| Numbered lists | ✅ | Preserved with `1.` numbering |
| Tables | ✅ | 7 table rows with pipe delimiters |
| Embedded image | ✅ | Included as inline base64 data URI |
| Text content | ✅ | All paragraphs preserved |

**Verdict:** DOCX conversion is **production-ready** — consistent with MarkItDown's mature DOCX support (via `mammoth` library internally). Low risk.

## Key Findings

### 1. PDF Text Extraction — Good With Caveats

MarkItDown extracts all PDF text content accurately. However:
- **Headings lack `#` markers** — they appear as plain text lines. Post-processing heuristics (font size, bold detection) or pdfminer layout analysis could restore heading levels.
- **Bullet artifacts** — PDF bullet characters render as `(cid:127)` instead of `•`. Simple regex cleanup (`(cid:\d+)` → `•`) resolves this.
- **Table fidelity varies** — simple tables convert well, but styled tables with merged cells or background colors can lose pipe delimiters.

### 2. PDF Image Extraction — PyMuPDF Required

MarkItDown does **not** extract or reference embedded PDF images in its Markdown output. This is the most significant gap.

**Recommended approach:** Use PyMuPDF (`fitz`) as a supplementary image extraction step:
1. MarkItDown converts PDF → Markdown (text + tables)
2. PyMuPDF extracts embedded images at original resolution
3. Image descriptions generated via GPT-4.1 vision (same as current HTML pipeline)
4. Merge step inserts image blocks into Markdown

This matches the pattern already used for HTML → Markdown conversion.

### 3. PPTX Conversion — Excellent, No Supplementation Needed

MarkItDown 0.1.5 includes **full speaker notes support** — each slide's notes appear under a `### Notes:` section. This was the primary concern for PPTX, and it's resolved without any additional tooling.

Image references are present in the output, though with generic filenames (`PictureN.jpg`). For the KB pipeline, python-pptx can be used to extract images by slide for higher-fidelity image-to-text mapping.

### 4. DOCX Conversion — Low Risk, Production-Ready

DOCX conversion is mature and reliable. All document elements (headings, lists, tables, images) are preserved. No supplementation needed.

## Limitations & Mitigations

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| PDF headings lack `#` markers | Medium | Post-process with heuristics: detect bold/large text lines and add heading markers |
| PDF bullet `(cid:N)` artifacts | Low | Regex replace `(cid:\d+)` → `•` in post-processing |
| PDF embedded images not referenced | High | Use PyMuPDF (`fitz`) for image extraction — 2-step pipeline |
| PDF styled tables partially break | Medium | Accept for Phase 1; consider pdfplumber table extraction for complex tables |
| PPTX image filenames generic | Low | Use python-pptx for precise image-to-slide mapping if needed |

## Recommendation

### 🟢 GO — Proceed with Epic 014

MarkItDown is viable for PDF, PPTX, and DOCX conversion with the following architecture:

| Format | Text Extraction | Image Extraction | Notes Extraction |
|--------|----------------|-----------------|-----------------|
| **PDF** | MarkItDown + post-processing | PyMuPDF (`fitz`) | N/A |
| **PPTX** | MarkItDown (native) | MarkItDown refs + python-pptx blobs | MarkItDown (native) |
| **DOCX** | MarkItDown (native) | MarkItDown (base64 inline) | N/A |

**Key dependencies for Epic 014:**
- `markitdown[pdf,pptx,docx]>=0.1.5` — core conversion library with format-specific extras
- `pymupdf>=1.27.0` — PDF image extraction only
- `python-pptx>=1.0.0` — optional, for precise PPTX image extraction

**No blockers identified.** The identified gaps (PDF headings, bullet artifacts, image extraction) all have straightforward mitigations that fit within the existing pipeline architecture.

---

## Appendix: Sample Output Excerpts

### PDF Markdown (first 500 chars)

```
Azure Knowledge Base Architecture Guide
Introduction
This document describes the architecture of the Azure Knowledge Base system. The system uses
Azure AI Search for retrieval-augmented generation (RAG) and Azure OpenAI Service for natural
language understanding.
System Architecture
The following diagram shows the high-level architecture of the system:
Component Overview
| Component | Service | Purpose | SKU |
| --------- | ------- | ------- | --- |
```

### PPTX Markdown (Slide 2 with speaker notes)

```markdown
<!-- Slide number: 2 -->
# System Components
Core Services
Azure AI Search — hybrid vector + keyword retrieval
Azure OpenAI — GPT-4.1 for generation and vision
Azure Blob Storage — KB article staging and serving
Azure Container Apps — serverless hosting
Azure Cosmos DB — conversation memory

### Notes:
Emphasize that all services communicate via managed identity. No connection strings
or API keys are stored in application code. The Container Apps use
DefaultAzureCredential for authentication.
```

### DOCX Markdown (excerpt)

```markdown
# Prerequisites

* Python 3.11+
* Azure CLI with active subscription
* Azure Developer CLI (azd)
* Docker Desktop

# Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| AI_SERVICES_ENDPOINT | Yes | Azure AI Services endpoint URL |
```
