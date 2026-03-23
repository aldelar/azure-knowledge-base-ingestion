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

### Test Group 1: Synthetic (Controlled)

Generated programmatically with reportlab (PDF), python-pptx (PPTX), python-docx (DOCX). All documents include: headings, paragraphs, bullet points, tables (including a 30-row cross-page table), embedded PNG images (3 types), hyperlinks to external content, and (for PPTX) speaker notes on every slide.

Three distinct image types stress-test extraction quality:
1. **Architecture diagram** — color-coded service boxes, directional arrows, and text labels
2. **Bar chart** — axes, data bars, category labels, and a legend
3. **Photo-like landscape** — pixel-level gradient with noise, organic ellipse shapes

Synthetic samples committed under `src/spikes/004-pdf-pptx-conversion/samples/`.

### Test Group 2: Real-World (Public Domain)

Real-world complex documents from public sources, committed under `src/spikes/004-pdf-pptx-conversion/samples/real-world/`. All documents downloadable via `download_real_world.py`.

**PDFs (3 documents):**

| Document | Size | Pages | Source Links | Images | Complexity |
|----------|-----:|------:|:---:|:---:|------------|
| **OWASP ASVS 4.0.3** | 1.1 MB | 71 | 377 | 73 | Security controls matrices, multi-level headings, cross-references |
| **NIST CSF 2.0** | 1.5 MB | ~32 | 103 | 13 | Government whitepaper, diagrams, multi-column layout, appendices |
| **Attention Is All You Need** (arXiv) | 2.2 MB | 8 | 113 | 3 | Academic paper, math equations, 2-column layout, bibliography |

**PPTXs (8 documents — Apache POI + Tika test fixtures):**

| Document | Size | Slides | Speaker Notes | Tables | Images |
|----------|-----:|:---:|:---:|:---:|:---:|
| **Apache POI SampleShow** | 39 KB | 2 | ✅ 2 | — | — |
| **Apache POI shapes** | 69 KB | 6 | — | ✅ 16 rows | ✅ 1 |
| **Apache POI table_test** | 29 KB | 1 | — | ✅ 7 rows | — |
| **Apache POI test (pptx2svg)** | 149 KB | 1 | — | — | — |
| **Tika test** | 37 KB | 3 | — | — | — |
| **Tika various** | 57 KB | 1 | ✅ 1 | ✅ 3 rows | — |
| **Tika embedded PDF** | 109 KB | 1 | — | — | ✅ 1 |
| **Tika comment** | 31 KB | 1 | — | — | — |

**DOCXs (4 documents):**

| Document | Size | Headings | Links | Tables | Images |
|----------|-----:|:---:|:---:|:---:|:---:|
| **Section 508 Word Guide** | 1.8 MB | 21 | 3 | 21 rows | 24 |
| **Tika testWORD** | 13 KB | 4 | 2 | 5 rows | — |
| **Tika testWORD_embedded** | 158 KB | — | — | — | 6 |
| **Tika testWORD_various** | 14 KB | — | 1 | 4 rows | — |

## Results

### Conversion Quality Matrix

| Format | Chars | Lines | Headings | Links | Table Rows | Image Refs |
|--------|------:|------:|---------:|------:|-----------:|-----------:|
| PDF    | 5,624 |    93 |        0 |     0 |         31 |          0 |
| PPTX   | 5,602 |   106 |       16 |     0 |         38 |          3 |
| DOCX   | 4,487 |    90 |        8 |     6 |         40 |          3 |

All three documents contain: 3 distinct image types (architecture diagram, bar chart, photo-like landscape), hyperlinks to external content, a short table, and a long table (30 data rows).

### PDF Conversion Findings

| Aspect | Status | Details |
|--------|--------|---------|
| Paragraph text | ✅ | All paragraph content preserved accurately |
| Sub-headings | ✅ | Present as plain text (e.g., "System Architecture", "Component Overview") |
| Heading markers | ⚠️ | No `#` Markdown formatting — headings are plain text, not styled |
| Table (simple) | ✅ | API Endpoints table rendered correctly with pipes and alignment |
| Table (styled) | ⚠️ | Component Overview table partially broken — some rows lose pipe delimiters |
| Long table (30 rows) | ✅ | 31 table rows in output — long table preserved as a single table across pages |
| Bullet points | ⚠️ | Rendered as `(cid:127)` — PDF character ID artifact instead of `•` or `-` |
| Image references | ❌ | MarkItDown produces **no** `![](...)` for embedded PDF images |
| Hyperlinks | ❌ | **All hyperlinks lost** — both inline and reference-style links stripped during conversion |
| Overall text fidelity | ✅ | All content words present and readable |

**PDF Image Extraction Comparison:**

| Approach | Images Found | Resolution | Format | Quality |
|----------|:----------:|-----------|--------|---------|
| MarkItDown native | 0 | N/A | N/A | No image extraction from PDF |
| PyMuPDF (fitz) | 3 | 600×400 (arch diagram), 500×350 (chart), 500×350 (photo) | PNG | ✅ Original resolution, lossless |

PyMuPDF extracts all three image types — architecture diagram (11 KB), bar chart (8 KB), and photo-like image (284 KB) — at their original resolution with no quality loss. The photo-like image with pixel-level noise and gradients preserved perfectly.

**Verdict:** MarkItDown extracts PDF text well but cannot extract embedded images. **PyMuPDF is required** for PDF image extraction — it extracts at original resolution with zero quality loss across all image types (diagrams, charts, and photographs).

### PPTX Conversion Findings

| Aspect | Status | Details |
|--------|--------|---------|
| Slide titles | ✅ | All 8 slide titles extracted as `# Title` headings |
| Slide body text | ✅ | Bullet points and content preserved accurately |
| Speaker notes | ✅ | **All 8/8 speaker notes included** under `### Notes:` sections |
| Tables (short) | ✅ | PPTX table rendered as pipe-delimited Markdown with headers |
| Long table (30 rows) | ✅ | 38 table rows in output — long table preserved as a single table |
| Image references | ✅ | `![name](PictureN.jpg)` — 3 images referenced (all types present) |
| Slide structure | ✅ | `<!-- Slide number: N -->` comments mark slide boundaries |
| Formatting | ✅ | Text hierarchy (title → body → notes) preserved |
| Hyperlinks | ❌ | **External hyperlinks lost** — link text preserved but URLs stripped |

**Speaker Notes Verification:**

All 5 speaker notes keywords were found in MarkItDown output:
- ✅ "managed identity"
- ✅ "connection strings"
- ✅ "DefaultAzureCredential"
- ✅ "data flow"
- ✅ "cost-effective"

**python-pptx cross-validation:** 8/8 slides have notes (1,671 total chars). MarkItDown output matches.

**PPTX Image Extraction:**

| Approach | Images Found | Details |
|----------|:----------:|---------|
| MarkItDown (in Markdown) | 3 | Referenced as `![name](PictureN.jpg)` — all 3 image types present |
| python-pptx | 3 | Full blob access at original resolution |

**PPTX Hyperlink Finding:**
External hyperlinks added to slides (e.g., links to Azure docs) are **not preserved** in the MarkItDown output. The link text appears (e.g., "Azure AI Search docs") but the URL (`https://learn.microsoft.com/azure/search/`) is stripped. This is similar to the PDF behavior. For PPTX, `python-pptx` can extract hyperlinks from shape runs as a supplementary step.

**Verdict:** MarkItDown PPTX conversion is **excellent** for content extraction. Speaker notes are included natively. **Hyperlinks require supplementation** — python-pptx can extract them.

### DOCX Conversion Findings (Spot Check)

| Aspect | Status | Details |
|--------|--------|---------|
| Headings | ✅ | 8 headings with `#` Markdown markers |
| Bullet lists | ✅ | Preserved with `*` markers |
| Numbered lists | ✅ | Preserved with `1.` numbering |
| Tables (short) | ✅ | 5-row env variables table with pipe delimiters |
| Long table (30 rows) | ✅ | 40 table rows in output — long table preserved as a single table |
| Embedded images | ✅ | All 3 image types included as inline base64 data URIs |
| Hyperlinks | ✅ | **6 hyperlinks preserved** as `[text](url)` — no post-processing needed |
| Text content | ✅ | All paragraphs preserved |

**DOCX Hyperlink Finding:**
Hyperlinks are **fully preserved** in the MarkItDown DOCX output:
```
[Azure AI Search documentation](https://learn.microsoft.com/azure/search/)
[Azure OpenAI Service](https://learn.microsoft.com/azure/ai-services/openai/)
[MarkItDown on GitHub](https://github.com/microsoft/markitdown)
```
This is because MarkItDown uses `mammoth` internally for DOCX, which handles hyperlinks natively.

**Verdict:** DOCX conversion is **production-ready** — headings, tables (including long tables), lists, images, and hyperlinks all preserved. No supplementation needed.

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

### 3. PPTX Conversion — Excellent, No Supplementation Needed for Content

MarkItDown 0.1.5 includes **full speaker notes support** — each slide's notes appear under a `### Notes:` section. This was the primary concern for PPTX, and it's resolved without any additional tooling.

Image references are present in the output, though with generic filenames (`PictureN.jpg`). For the KB pipeline, python-pptx can be used to extract images by slide for higher-fidelity image-to-text mapping.

### 4. DOCX Conversion — Low Risk, Production-Ready

DOCX conversion is mature and reliable. All document elements (headings, lists, tables, images, **and hyperlinks**) are preserved. No supplementation needed.

### 5. Hyperlink Extraction — Critical Gap for PDF and PPTX ⚠️

| Format | Hyperlinks in Source | Hyperlinks in Output | Status |
|--------|:-------------------:|:--------------------:|--------|
| **PDF** | 8 (inline + reference list) | 0 | ❌ Completely lost |
| **PPTX** | 6 (slide text + references slide) | 0 | ❌ Completely lost (text preserved, URLs stripped) |
| **DOCX** | 6 (inline + reference list) | 6 | ✅ Fully preserved as `[text](url)` |

**Impact:** Hyperlinks in PDF and PPTX are completely lost during MarkItDown conversion. This is significant for KB articles that reference external documentation or Azure service pages.

**Mitigations:**
- **PDF:** Use PyMuPDF to extract link annotations (`page.get_links()`) — returns URL + bounding box. Post-process to match link text to URLs.
- **PPTX:** Use python-pptx to extract hyperlinks from shape runs (`run.hyperlink.address`) — straightforward supplementation.
- **DOCX:** No action needed — links are preserved natively.

This follows the same pre/post-processing pattern already used for HTML converters.

### 6. Long Table Handling — All Formats Pass ✅

| Format | Table Rows in Source | Table Rows in Output | Status |
|--------|:-------------------:|:--------------------:|--------|
| **PDF** | 31 (header + 30 data) | 31 | ✅ Single table preserved |
| **PPTX** | 31 (header + 30 data) | 38 | ✅ Single table preserved |
| **DOCX** | 31 (header + 30 data) | 40 | ✅ Single table preserved |

All three converters handle the 30-row table as a single Markdown table — no splitting or truncation at page/slide boundaries. The PDF table uses `repeatRows=1` to repeat the header row on each page, and MarkItDown correctly merges these into one table.

## Real-World Validation

The synthetic findings were validated against **15 real-world public domain documents** — 3 PDFs, 8 PPTXs, and 4 DOCXs — sourced from OWASP, NIST, arXiv, Apache POI, Apache Tika, and the US Section 508 program.

### Real-World PDF Results (3 documents)

| Metric | OWASP ASVS (71p) | NIST CSF 2.0 (~32p) | arXiv Attention (8p) |
|--------|:-----------------:|:-------------------:|:--------------------:|
| Text chars | ✅ 180,683 | ✅ 69,023 | ✅ 39,470 |
| Headings with `#` | ✅ 70 (bookmarks) | ⚠️ 0 | ⚠️ 0 |
| Hyperlinks `[text](url)` | ❌ 0 / 377 | ❌ 0 / 103 | ❌ 0 / 113 |
| Bare URLs in text | 18 | 2 | 1 |
| Table rows (pipe) | ❌ 0 | ❌ 0 | ❌ 0 |
| Image refs | ❌ 0 | ❌ 0 | ❌ 0 |
| PyMuPDF images | 73 | 13 | 3 |

**Key observations:**
- **All 593 hyperlinks across 3 PDFs → 0 extracted.** Hyperlink loss is universal and confirmed at scale.
- **All 89 images across 3 PDFs → 0 in Markdown.** PyMuPDF extracts all at original resolution.
- **Tables:** Complex real-world tables (OWASP security matrices, NIST reference tables) render as plain text — 0 pipe-delimited rows across all 3 PDFs. This is worse than synthetic tests.
- **Headings:** Only OWASP ASVS (which has PDF bookmarks) gets `#` markers. NIST and arXiv PDFs — which lack bookmarks — get none. This confirms that heading extraction depends on PDF bookmark metadata.

### Real-World PPTX Results (8 documents)

| Document | Slides | Speaker Notes | Tables | Images | Links |
|----------|:---:|:---:|:---:|:---:|:---:|
| POI SampleShow | 2 | ✅ 2/2 | — | — | ❌ 0 |
| POI shapes | 6 | — | ✅ 16 | ✅ 1 | ⚠️ 1 bare |
| POI table_test | 1 | — | ✅ 7 | — | — |
| POI test | 1 | — | — | — | — |
| Tika test | 3 | — | — | — | — |
| Tika various | 1 | ✅ 1 | ✅ 3 | — | — |
| Tika embedded | 1 | — | — | ✅ 1 | — |
| Tika comment | 1 | — | — | — | — |

**Key observations:**
- **Speaker notes preserved** where present (3/3 slides with notes → all extracted as `### Notes:`)
- **Tables extracted** in pipe-delimited format (26 rows total across 3 PPTXs with tables)
- **Images referenced** in Markdown where present (`![name](PictureN.jpg)`)
- **Hyperlinks universally lost** — consistent with synthetic findings

### Real-World DOCX Results (4 documents)

| Document | Headings | Links | Tables | Images |
|----------|:---:|:---:|:---:|:---:|
| Section 508 Guide | ✅ 21 | ✅ 3 | ✅ 21 rows | ✅ 24 |
| Tika testWORD | ✅ 4 | ✅ 2 | ✅ 5 rows | — |
| Tika embedded | — | — | — | ✅ 6 |
| Tika various | — | ✅ 1 | ✅ 4 rows | — |

**Key observations:**
- **Section 508 Word Guide (1.8 MB):** Production-quality result — 21 headings, 3 hyperlinks, 21 table rows, **24 embedded images** all preserved. This is a complex real-world government document and MarkItDown handles it excellently.
- **Hyperlinks preserved** in all DOCX files that contain them (6/6 links across 3 documents)
- **DOCX conversion is production-ready** — confirmed with real-world documents

### Cross-Format Real-World Summary

| Capability | PDF (3 docs) | PPTX (8 docs) | DOCX (4 docs) |
|-----------|:---:|:---:|:---:|
| Text extraction | ✅ | ✅ | ✅ |
| Heading markers | ⚠️ Only with bookmarks | ✅ | ✅ |
| Hyperlinks | ❌ 0/593 | ❌ 0 | ✅ 6/6 |
| Tables (pipe) | ❌ 0 rows | ✅ 26 rows | ✅ 30 rows |
| Image references | ❌ | ✅ (where present) | ✅ (30 images) |
| Speaker notes | N/A | ✅ 3/3 | N/A |

### Verdict

Real-world testing with 15 public domain documents **confirms and strengthens** the synthetic findings:
- PDF hyperlink and image gaps are **severe at scale** (593 links lost, 89 images lost across 3 documents)
- Complex PDF tables are **worse than synthetic** (0 pipe-delimited rows vs. 31 in synthetic)
- PPTX speaker notes are **reliably extracted** in real-world presentations
- DOCX conversion is **production-ready** — even a complex 1.8 MB government guide with 24 images converts cleanly
- The GO recommendation stands — supplementation with PyMuPDF for PDF and python-pptx for PPTX hyperlinks is non-negotiable for production use

## Limitations & Mitigations

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| PDF headings lack `#` markers (simple PDFs) | Medium | Post-process with heuristics — or ensure PDFs have bookmarks (real-world PDFs with bookmarks get proper `#` markers) |
| PDF bullet `(cid:N)` artifacts | Low | Regex replace `(cid:\d+)` → `•` in post-processing |
| PDF embedded images not referenced | High | Use PyMuPDF (`fitz`) for image extraction — 2-step pipeline |
| PDF hyperlinks completely lost | **High** | Use PyMuPDF `page.get_links()` to extract URLs + bounding boxes, then match to text |
| PDF complex tables not extracted | **High** | Simple tables work; complex real-world tables (merged cells, multi-line) render as plain text. Consider pdfplumber for table extraction |
| PDF styled tables partially break | Medium | Accept for Phase 1; consider pdfplumber table extraction for complex tables |
| PPTX hyperlinks lost (URLs stripped) | **High** | Use python-pptx `run.hyperlink.address` to extract URLs from slide shapes |
| PPTX image filenames generic | Low | Use python-pptx for precise image-to-slide mapping if needed |

## Recommendation

### 🟢 GO — Proceed with Epic 014

MarkItDown is viable for PDF, PPTX, and DOCX conversion with the following architecture:

| Format | Text Extraction | Image Extraction | Hyperlink Extraction | Notes Extraction |
|--------|----------------|-----------------|---------------------|-----------------|
| **PDF** | MarkItDown + post-processing | PyMuPDF (`fitz`) | PyMuPDF (`page.get_links()`) | N/A |
| **PPTX** | MarkItDown (native) | MarkItDown refs + python-pptx blobs | python-pptx (`run.hyperlink.address`) | MarkItDown (native) |
| **DOCX** | MarkItDown (native) | MarkItDown (base64 inline) | MarkItDown (native — `[text](url)`) | N/A |

**Key dependencies for Epic 014:**
- `markitdown[pdf,pptx,docx]>=0.1.5` — core conversion library with format-specific extras
- `pymupdf>=1.27.0` — PDF image extraction + hyperlink extraction
- `python-pptx>=1.0.0` — PPTX hyperlink extraction + precise image extraction

**New finding: hyperlink extraction gap.** PDF and PPTX hyperlinks are completely lost during conversion. This follows the same pre/post-processing pattern already used for HTML converters — the mitigation is straightforward using PyMuPDF and python-pptx respectively. DOCX hyperlinks are preserved natively.

**No blockers identified.** The identified gaps (PDF headings, bullet artifacts, image extraction, and hyperlink extraction for PDF/PPTX) all have straightforward mitigations that fit within the existing pipeline architecture.

---

## Appendix: Sample Output Excerpts

### PDF Markdown (excerpt showing hyperlinks lost)

```
Azure Knowledge Base Architecture Guide
Introduction
This document describes the architecture of the Azure Knowledge Base system. The system uses
Azure AI Search for retrieval-augmented generation (RAG) and Azure OpenAI Service for natural
language understanding. For more details, see the MarkItDown GitHub repository.
```

Note: The original PDF contained hyperlinks (e.g., `Azure AI Search` linked to `https://learn.microsoft.com/azure/search/`) — all links are stripped from the text output.

### PDF Markdown (long table excerpt)

```
Azure Resource Inventory
| # | Resource Name | Type | Region | Status | Monthly Cost |
| - | ------------- | ---- | ------ | ------ | ------------ |
| 1 | kb-agent-container-app-01 | Container App | East US 2 | Running | $45.00 |
| 2 | kb-agent-cosmos-db-02 | Cosmos DB | West US 3 | Provisioned | $120.50 |
...
| 30 | kb-agent-virtual-network-30 | Virtual Network | North Europe | Scaling | $0.00 |
```

All 30 data rows preserved as a single Markdown table.

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
Documentation: Azure AI Search docs

### Notes:
Emphasize that all services communicate via managed identity. No connection strings
or API keys are stored in application code.
```

Note: "Azure AI Search docs" was a hyperlink to `https://learn.microsoft.com/azure/search/` in the original PPTX — the URL is stripped.

### DOCX Markdown (excerpt showing hyperlinks preserved)

```markdown
# Prerequisites

* Python 3.11+
* Azure CLI with active subscription
* Azure Developer CLI (azd)
* Docker Desktop

# References

* [Azure AI Search documentation](https://learn.microsoft.com/azure/search/)
* [Azure OpenAI Service](https://learn.microsoft.com/azure/ai-services/openai/)
* [MarkItDown on GitHub](https://github.com/microsoft/markitdown)
```

DOCX hyperlinks are fully preserved as `[text](url)` — no post-processing needed.

### Real-World: NIST CSF 2.0 PDF (excerpt)

```
The NIST Cybersecurity
Framework (CSF) 2.0

National Institute of Standards and Technology
This publication is available free of charge from: https://doi.org/10.6028/NIST.CSWP.29

February 26, 2024
```

Note: All 103 hyperlinks in the source PDF are lost. Only 2 bare URLs survive as plain text.

### Real-World: arXiv "Attention Is All You Need" (excerpt)

The arXiv PDF with 2-column layout produces garbled initial output — the header metadata characters are extracted one-per-line instead of as words (e.g., the arXiv ID `1706.03762` appears as `7`, `1`, `0`, `2`, `c`, `e`, `D`, `6`...). The body text is extracted correctly, but multi-column layout causes paragraph interleaving — this is a known limitation of pdfminer-based extraction with multi-column PDFs.

### Real-World: Section 508 Word Guide (DOCX excerpt)

```markdown
![Accessible Electronic Document Community of Practice (AED COP) Logo](data:image/jpeg;base64...)

Microsoft Word 2016 Basic Authoring and Testing Guide
Section 508 Accessibility Guidance

[Document Formatting 2](#_Toc528312294)
[1. Is the file name descriptive...? 2](#_Toc528312295)
```

A complex 1.8 MB government document with 24 images, 21 headings, and 3 hyperlinks — all converted cleanly. This validates DOCX as production-ready for real-world use.

### Real-World: Apache POI SampleShow (PPTX with speaker notes)

```markdown
<!-- Slide number: 1 -->
# Title of the first slide
Subtitle of the first slide
This bit is in italic green

### Notes:
I am the notes of the first slide

<!-- Slide number: 2 -->
# This is the second slide
It has bullet points on it

### Notes:
These are the notes of the 2nd slide
THIS LINE IS BOLD
```

Speaker notes reliably extracted from real-world PPTX files, not just synthetic samples.
