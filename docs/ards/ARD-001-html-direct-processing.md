# ARD-001: HTML-Direct Processing — Eliminate PDF Conversion

> **Status:** Accepted
> **Date:** 2026-02-13
> **Decision Makers:** Engineering Team

## Context

The ingestion pipeline processes HTML knowledge base articles (DITA-generated) containing embedded images into Markdown for downstream indexing. The initial approach converted HTML → PDF (via Playwright headless Chromium) to unlock Azure Content Understanding's figure detection, which only works on PDF and image inputs.

This conversion introduced significant complexity:

- **Playwright/Chromium dependency** — headless browser required at build and runtime
- **Image quality degradation** — source PNGs (13–40 KB each) are rasterized into the PDF then re-cropped via bounding polygon parsing, losing fidelity
- **Fragile image extraction** — bounding polygon coordinates from CU must be translated to PDF page coordinates (DPI-aware), cropped via PyMuPDF, and saved via Pillow
- **Additional dependencies** — `playwright`, `PyMuPDF`, `Pillow` added to the dependency tree

## Decision

**Process HTML directly for text extraction and analyze each source image individually.** No HTML → PDF conversion step.

The pipeline uses two parallel CU calls:

1. **HTML → `prebuilt-documentSearch`** — extracts text, tables, headings, and a summary as Markdown
2. **Each image → `kb-image-analyzer`** (custom CU analyzer) — produces a `Description`, `UIElements`, and `NavigationPath` per image

Results are merged by correlating image positions from the HTML DOM with the CU Markdown output.

## Alternatives Considered

### Alternative 1: PDF Pipeline (Rejected)

Convert HTML → PDF via Playwright, send PDF to CU, crop figures from PDF using bounding polygons, re-analyze cropped images.

- **Pros:** Single CU call gets text + figures together; richer JSON response (paragraphs, hyperlinks, figures arrays)
- **Cons:** Chromium dependency, image quality loss, bounding polygon complexity, 3 additional Python packages, slower pipeline

### Alternative 2: Base64-Embedded Images in HTML (Rejected)

Encode images as `data:image/png;base64,...` data URIs in the HTML `<img>` tags before sending to CU.

- **Result:** Tested empirically — CU strips data URIs. Output was identical to plain HTML (0 figures, 0 hyperlinks). Not viable.

### Alternative 3: URL-Based HTML Input (Not Pursued)

Pass a publicly accessible URL to CU so it can resolve `<img src>` references by fetching images from the server.

- **Cons:** Requires articles to be hosted at accessible URLs; source articles are internal/offline. Does not solve the fundamental limitation that CU's figure analysis is PDF/image-only.

## Consequences

### Positive

- **Simpler dependency tree** — eliminates `playwright`, `PyMuPDF`, and `Pillow`
- **Original image quality preserved** — source PNGs are used directly, no rasterization or re-cropping
- **Better image descriptions** — each image gets dedicated CU analysis with a domain-tuned prompt, rather than generic figure captions from PDF analysis
- **Faster pipeline** — no headless browser rendering step
- **Hyperlinks recoverable** — parsed directly from the HTML DOM (CU strips URLs from HTML input, but the link labels survive in Markdown; URLs are re-injected by text-matching)

### Negative

- **N+1 API calls per article** — 1 HTML analysis + N image analyses (same count as the two-pass PDF approach, but more explicit)
- **Position matching is heuristic** — correlating CU Markdown positions with HTML `<img>` positions requires text-matching against surrounding content. Works reliably for DITA-generated HTML (each image follows a unique step instruction) but may need adaptation for other HTML structures
- **Less structured JSON** — CU returns no `paragraphs`, `hyperlinks`, or `tables` arrays for HTML input; compensated by HTML DOM parsing with BeautifulSoup

## Evidence

Empirical testing documented in [architecture-research.md](../research/architecture-research.md) and [architecture-proposal.md](../research/architecture-proposal.md):

| Feature | HTML → CU | PDF → CU |
|---------|-----------|----------|
| Markdown quality | High (2,919 chars, tables, headings) | High (7,305 chars, figures inline) |
| Figures detected | 0 | 4 |
| Hyperlinks in JSON | 0 | 1 |
| Summary field | Good | Good |
| Image quality | Original PNGs (lossless) | Rasterized + cropped (lossy) |
| Dependencies | `beautifulsoup4` only | `playwright`, `PyMuPDF`, `Pillow` |

## References

- [Architecture Proposal — Option 1: HTML-Direct Pipeline](../research/architecture-proposal.md)
- [Architecture Research — Dropping the PDF Conversion Step](../research/architecture-research.md)
- [Analyzer Options Research](../research/analyzer-options.md)
