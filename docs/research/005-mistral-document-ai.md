# Research: Mistral Document AI as Alternative to Azure Content Understanding

> **Date:** 2026-02-20
> **Status:** Draft
> **Model reviewed:** `mistral-document-ai-2512` (Mistral OCR 3, released December 18, 2025)

---

## Context

Our current pipeline uses **Azure Content Understanding (CU)** for two tasks:

1. **HTML → markdown** — `prebuilt-documentSearch` extracts text, tables, headings, and a summary from the HTML article
2. **Image → description** — a custom `kb-image-analyzer` (based on `prebuilt-image`) extracts `Description`, `UIElements`, and `NavigationPath` from each article image individually

This research evaluates whether **Mistral Document AI** (`mistral-document-ai-2512`), now available in the Microsoft Foundry model catalog, could serve as an alternative or second option for the document processing stage.

### Key Requirements to Preserve

- **Image references in output markdown** — each chunk in AI Search carries `image_urls[]` pointing to source images in blob storage
- **Source images served to agent LLM** — the web app's vision middleware fetches actual images and injects them into the LLM conversation as base64; the agent reasons over the real images, not just text descriptions
- **Image descriptions for search** — AI-generated text descriptions are embedded alongside paragraphs to boost vector similarity for visual concepts during search
- **Hyperlink preservation** — original `<a href>` URLs from the HTML must survive in the output

> **Note on summary:** CU's `prebuilt-documentSearch` auto-generates a summary field that `fn-convert` writes to `summary.txt`. However, `fn-index` never reads or indexes this file — it only consumes `article.md`. Summary is therefore **not a pipeline requirement** and would simply be dropped with Mistral.

---

## 1. Model Overview

### What Is It

**Mistral Document AI** is Mistral AI's enterprise-grade document processing model, branded as "OCR 3" in Mistral's own documentation. On Azure, it's deployed as `mistral-document-ai-2512` (the `2512` suffix = December 2025 release). It is classified as an **Image-to-Text** model in the Foundry catalog.

Mistral OCR 3 replaces the now-retired `Mistral-OCR-2503` model (retirement date: January 30, 2026).

### Capabilities

| Capability | Details |
|---|---|
| **Input formats** | PDF, images (PNG, JPEG/JPG, AVIF, etc.), PPTX, DOCX |
| **Output format** | Markdown (with optional HTML tables), JSON |
| **HTML input** | **Not supported natively** — HTML files cannot be sent directly |
| **Max pages (Azure)** | 30 pages, max 30MB PDF |
| **Max pages (Mistral direct)** | Higher limits via direct API |
| **Languages** | English (primary), multilingual support |
| **Tool calling** | No |
| **Image extraction** | Yes — detects embedded images, returns bounding boxes and optional base64 |
| **Table extraction** | Yes — configurable as `null` (inline), `markdown`, or `html` (with colspan/rowspan) |
| **Hyperlink extraction** | Yes — returns hyperlinks when available |
| **Header/footer extraction** | Yes (new in 2512) — via `extract_header` / `extract_footer` parameters |
| **Structured output** | Via "Annotations" feature — extract typed fields with JSON schema |
| **Batch processing** | Supported via Mistral Batch Inference service |
| **Pricing** | $2 / 1,000 pages ($1 / 1,000 pages with batch discount) |

### Key Strengths (from benchmarks)

- **74% overall win rate** over Mistral OCR 2 on forms, scanned documents, complex tables, and handwriting
- State-of-the-art accuracy against both enterprise and AI-native OCR solutions
- Robust handling of compression artifacts, skew, distortion, low DPI, background noise
- Reconstructs complex table structures with headers, merged cells, multi-row blocks, column hierarchies
- Outputs HTML table tags with `colspan`/`rowspan` to fully preserve layout

### API Endpoint

On Mistral's platform: `POST /v1/ocr` with the `mistralai` Python SDK.
On Azure Foundry: deployed as a serverless endpoint with the same `/v1/ocr` path.

---

## 2. API & SDK Details

### Python SDK Usage (Mistral Platform)

```python
from mistralai import Mistral

client = Mistral(api_key="...")

# OCR a PDF from URL
ocr_response = client.ocr.process(
    model="mistral-ocr-latest",  # or "mistral-ocr-2512"
    document={
        "type": "document_url",
        "document_url": "https://example.com/document.pdf"
    },
    table_format="html",          # "html" | "markdown" | None
    extract_header=True,          # new in 2512
    extract_footer=True,          # new in 2512
    include_image_base64=True     # return base64-encoded extracted images
)
```

### Azure Foundry Usage

On Azure, the model is deployed as a serverless API and called via REST:

```bash
curl --request POST \
  --url https://<your-endpoint>/v1/ocr \
  --header 'Authorization: Bearer <api-key>' \
  --header 'Content-Type: application/json' \
  --data '{
    "model": "mistral-document-ai-2512",
    "document": {
      "type": "document_url",
      "document_url": "data:application/pdf;base64,<base64-encoded-pdf>"
    },
    "include_image_base64": true
  }'
```

> **Azure limitation:** The Azure deployment requires **base64-encoded data** for the `document_url` parameter. Direct HTTP URLs to PDFs are not supported on Azure — only the Mistral platform supports fetching from URLs.

### Response Structure

```json
{
  "pages": [
    {
      "index": 0,
      "markdown": "# Document Title\n\nParagraph text...\n\n![img-0.jpeg](img-0.jpeg)\n\n...",
      "images": [
        {
          "id": "img-0.jpeg",
          "top_left_x": 100, "top_left_y": 200,
          "bottom_right_x": 500, "bottom_right_y": 600,
          "image_base64": "data:image/jpeg;base64,..."
        }
      ],
      "tables": [
        {
          "id": "tbl-0.html",
          "content": "<table>...</table>"
        }
      ],
      "hyperlinks": [...],
      "header": "Page Header Text",
      "footer": "Page 1 of 10",
      "dimensions": { "width": 612, "height": 792 }
    }
  ],
  "model": "mistral-ocr-2512",
  "usage_info": { ... }
}
```

**Critical observation for our use case:** When Mistral OCR detects images in a PDF, it:
1. Replaces them with **markdown placeholders** in the page text: `![img-0.jpeg](img-0.jpeg)`
2. Returns the **bounding box** coordinates for each image
3. Optionally returns the **base64-encoded image data** (via `include_image_base64=True`)

This means the output markdown has clear, positioned image references — exactly what we need for our chunking + indexing pipeline.

---

## 3. Document AI Services Stack

Mistral offers three services under the Document AI umbrella, all accessible via `client.ocr.process` / `/v1/ocr`:

| Service | Purpose | Relevance to Our Pipeline |
|---|---|---|
| **OCR Processor** | Extract text, tables, images, hyperlinks → markdown | Core replacement for CU's HTML text extraction |
| **Annotations** | Structured data extraction with JSON schema (fields, types) | Could replace CU's `fieldSchema` for custom field extraction |
| **Document QnA** | Combine OCR with LLM for question-answering over documents | Not directly relevant — our agent does this downstream |

---

## 4. Comparison: Azure Content Understanding vs Mistral Document AI

### Feature-by-Feature

| Feature | Azure Content Understanding | Mistral Document AI (OCR 3) |
|---|---|---|
| **HTML input (direct)** | ✅ Binary upload or URL | ❌ Not supported |
| **PDF input** | ✅ | ✅ (up to 30 pages / 30MB on Azure) |
| **Image input** | ✅ | ✅ (PNG, JPEG, AVIF, etc.) |
| **DOCX / PPTX input** | ❌ | ✅ |
| **Markdown output** | ✅ | ✅ |
| **Image detection in PDF** | ✅ (with figure description/analysis) | ✅ (with bounding boxes + base64 extraction) |
| **Image description generation** | ✅ Built-in (`enableFigureDescription`) | ❌ OCR only — no AI descriptions of images |
| **Hyperlink extraction** | ✅ (PDF only, not from HTML) | ✅ (when available in source) |
| **Table extraction** | ✅ (HTML/markdown format) | ✅ (null/markdown/HTML with colspan/rowspan) |
| **Summary generation** | ✅ (`prebuilt-documentSearch`) | ❌ Not built-in |
| **Custom field extraction** | ✅ (`fieldSchema`) | ✅ (Annotations with JSON schema) |
| **Confidence scores** | ✅ | ❌ |
| **Header/footer separation** | ❌ | ✅ (new in 2512) |
| **Batch processing** | Via async API | ✅ Native batch support (50% discount) |
| **Pricing (text extraction)** | Per-page pricing (varies by analyzer) | $2 / 1,000 pages ($1 batch) |
| **Azure managed identity** | ✅ Native | ✅ Microsoft Entra ID / managed identity via `DefaultAzureCredential` (`Cognitive Services User` role) |
| **Self-hosting** | ❌ | ✅ Available for enterprise |

### Key Differences for Our Pipeline

1. **No native HTML input** — Mistral cannot process HTML directly. We'd need to render HTML → PDF first (bringing back the Playwright dependency we dropped in ARD-001).

2. **No AI image descriptions** — Mistral OCR extracts images from PDFs and returns them as base64 blobs with bounding boxes, but it does NOT generate natural-language descriptions. For our pipeline, we still need GPT-4.1 (vision) to describe each image.

3. **Image extraction is better scoped** — Mistral explicitly returns each detected image as a separate entry with coordinates and base64, making it easy to map images back to their position in the markdown. CU requires parsing `D(page,x1,y1,...,x8,y8)` bounding polygon format and cropping via PyMuPDF.

4. **No summary field** — CU's `prebuilt-documentSearch` generates a summary automatically. With Mistral, there is no built-in equivalent. However, this is **not a gap in practice** — our `fn-index` pipeline never reads or indexes the summary; it only consumes `article.md`. The `summary.txt` file is a dead artifact. No replacement needed.

5. **Hyperlinks returned from PDF** — Mistral extracts hyperlinks from PDFs (returned in the `hyperlinks` field). This could solve the problem we had with CU dropping hyperlinks from HTML input.

---

## 5. Proposed Alternative Architecture: HTML → PDF → Mistral OCR

### Pipeline Flow

Since Mistral Document AI does not accept HTML, the pipeline would be:

```
kb/staging/<article>/
  index.html + images/*.image
  │
  ▼  Step 1: Render HTML → PDF (Playwright headless Chromium)
  │  → article.pdf (images rendered inline)
  │
  ▼  Step 2: PDF → Mistral OCR (mistral-document-ai-2512)
  │  → Structured markdown with image placeholders
  │  → Extracted images as base64 (from PDF rendering)
  │  → Hyperlinks, tables, headers/footers
  │
  ▼  Step 3: Map Mistral-extracted images to original source images
  │  • Use HTML marker injection strategy (see §5a below)
  │  • Markers in OCR output identify each source filename
  │  • Goal: reference ORIGINAL source images (higher quality than PDF-rendered)
  │
  ▼  Step 4: Generate image descriptions (GPT-4.1)
  │  • Send each original source image to GPT-4.1 (vision)
  │  • Prompt for Description, UIElements, NavigationPath
  │  • This replaces CU's custom kb-image-analyzer
  │
  ▼  Step 5: Merge & Reconstruct
  │  • Replace image placeholders with description blocks + image links
  │  • Inject hyperlinks if not already in markdown
  │  • Output: article.md + images/*.png
  │
kb/serving/<article>/
  article.md + images/*.png
  │
  ▼  Existing fn-index pipeline (unchanged)
  │  Chunk by headings → embed → push to AI Search
```

### What This Preserves

- ✅ **Source images in blob storage** — original images are copied to serving layer, referenced by markdown
- ✅ **Image URLs in search chunks** — `image_urls[]` field populated per chunk
- ✅ **Vision middleware works** — agent LLM receives actual source images for visual reasoning
- ✅ **Image descriptions for search** — generated by GPT-4.1 in Step 4, embedded in chunk text for vector similarity
- ✅ **Hyperlinks** — extracted by Mistral from the PDF rendering
- ~~Summary~~ — not needed; `fn-index` never uses it

### 5a. Image-to-Source Mapping Strategy: HTML Marker Injection

**The problem:** Mistral OCR extracts images from the rendered PDF and returns them as `img-0.jpeg`, `img-1.jpeg`, etc. We need to map each extracted image back to the original source file (e.g., `images/architecture-diagram.png`) so we can:
- Reference original high-quality images in the article markdown
- Serve them from blob storage URLs via `image_urls[]` in search chunks
- Feed them to the agent LLM for visual reasoning (vision middleware)

We want a strategy that is **simple and deterministic** — no complex image comparison or LLM processing.

#### Recommended: Inject Visible Text Markers Before Each Image

Before rendering HTML → PDF with Playwright, pre-process the HTML to inject a small visible text marker immediately before each `<img>` tag that references a source image in our folder.

**Before injection:**
```html
<p>The architecture is shown below:</p>
<img src="images/architecture-diagram.png" alt="Architecture">
<p>As you can see, the pipeline has three stages.</p>
```

**After injection:**
```html
<p>The architecture is shown below:</p>
<div style="font-size: 6px; color: #aaa; margin: 0; padding: 0; line-height: 1;">⟦IMG:architecture-diagram.png⟧</div>
<img src="images/architecture-diagram.png" alt="Architecture">
<p>As you can see, the pipeline has three stages.</p>
```

When Playwright renders this to PDF and Mistral OCR processes it, the output markdown will contain:
```markdown
The architecture is shown below:

⟦IMG:architecture-diagram.png⟧

![img-0.jpeg](img-0.jpeg)

As you can see, the pipeline has three stages.
```

**Mapping is now trivial:** scan the markdown for `⟦IMG:<filename>⟧` markers, then associate the next `![img-N.jpeg](img-N.jpeg)` placeholder with that source file.

#### Implementation Sketch

```python
import re
from pathlib import Path


def inject_image_markers(html: str) -> str:
    """Inject source-filename markers before each <img> tag in the HTML.

    The markers are small visible text that Mistral OCR will read and include
    in the output markdown, enabling deterministic image-to-source mapping.
    """
    def _add_marker(match: re.Match) -> str:
        img_tag = match.group(0)
        src_match = re.search(r'src=["\']([^"\']+)["\']', img_tag)
        if src_match:
            filename = Path(src_match.group(1)).name
            marker = (
                f'<div style="font-size:6px;color:#aaa;margin:0;padding:0;'
                f'line-height:1;">\u27e6IMG:{filename}\u27e7</div>'
            )
            return marker + img_tag
        return img_tag

    return re.sub(r'<img\b[^>]*/?>', _add_marker, html)


def map_images_from_markdown(markdown: str) -> dict[str, str]:
    """Parse Mistral OCR markdown to map img-N placeholders to source filenames.

    Returns dict like {"img-0.jpeg": "architecture-diagram.png", ...}
    """
    mapping: dict[str, str] = {}
    lines = markdown.split('\n')
    pending_source: str | None = None

    for line in lines:
        # Look for our injected marker
        marker_match = re.search(r'\u27e6IMG:(.+?)\u27e7', line)
        if marker_match:
            pending_source = marker_match.group(1)
            continue
        # Look for Mistral image placeholder
        img_match = re.search(r'!\[([^\]]*)\]\(([^)]+)\)', line)
        if img_match and pending_source:
            placeholder_id = img_match.group(2)  # e.g. "img-0.jpeg"
            mapping[placeholder_id] = pending_source
            pending_source = None

    return mapping
```

#### Why This Works

| Property | Assessment |
|---|---|
| **OCR readability** | 6px text is small but visible; OCR models excel at reading text — this will be captured |
| **Deterministic** | Direct filename → placeholder mapping via text, no probabilistic matching |
| **No image processing** | No perceptual hashing, pixel comparison, or embedding similarity needed |
| **Robust to quality loss** | Works regardless of PDF rendering quality or JPEG compression |
| **Low complexity** | ~30 lines of Python for injection + parsing |
| **Marker uniqueness** | `⟦IMG:...⟧` uses Unicode mathematical angle brackets — unlikely to appear in source HTML |

#### Alternative Strategies Considered

| Strategy | Pros | Cons | Verdict |
|---|---|---|---|
| **Sequential correlation** (img-0 = first `<img>`, img-1 = second, etc.) | Zero setup | Fragile — CSS reordering, missing images, decorators can break mapping | Fallback only |
| **Perceptual hashing** (pHash/dHash comparing extracted vs source) | Handles reordering | PDF rendering degrades quality; needs `imagehash` + Pillow deps; may have false positives | Over-engineered |
| **Visual embedding similarity** (encode both images with a vision model) | Robust matching | Expensive (LLM call per image pair); overkill | Rejected |
| **Alt-text enrichment** (inject filename into `alt` attribute) | No visual impact | Mistral may or may not include alt text in output; unreliable | Rejected |
| **Hidden text** (`font-size: 0` or `display: none`) | No visual impact | OCR may not detect invisible text; CSS hidden text often ignored by renderers | Rejected |

#### Validation Plan for Spike

1. Inject markers into a sample HTML article
2. Render to PDF with Playwright, visually confirm markers appear near images
3. Process PDF with Mistral OCR, confirm markers appear in output markdown
4. Run `map_images_from_markdown()` and verify correct source file mapping
5. Edge cases to test: adjacent images (no text between them), images inside tables, images in list items

### Trade-offs vs Current CU Pipeline

| Aspect | Current (CU) | Proposed (Mistral + LLM) |
|---|---|---|
| **HTML → PDF rendering** | ❌ Dropped (ARD-001) | ✅ Required again |
| **Image extraction quality** | CU returns bounding polygons, requires PyMuPDF cropping | Mistral returns clean base64 images directly |
| **Image descriptions** | Custom CU analyzer (`kb-image-analyzer`) | GPT-4.1 vision call |
| **Summary** | Built-in to `prebuilt-documentSearch` | Not needed (`fn-index` never indexes it) |
| **Azure managed identity** | ✅ Native RBAC | ✅ Microsoft Entra ID / managed identity via `DefaultAzureCredential` |
| **Dependencies** | `azure-ai-contentunderstanding` SDK | `mistralai` SDK (or REST) + Playwright |
| **API calls per article** | 1 (HTML) + N (images) = N+1 CU calls | 1 (PDF→Mistral) + N (image→GPT-4.1) |
| **Cost** | ~$0.033/article (see §6) | ~$0.026/article (see §6) |
| **Vendor lock-in** | Azure-only | Mistral available on Azure, self-hosted, or direct API |
| **Image mapping** | Parse HTML DOM for `<img>` positions | Mistral provides image positions in markdown via placeholders |

---

## 6. Cost Comparison (Estimated)

### What Is a "Page" — Normalization

CU and Mistral count **pages** differently, which matters for cost comparison:

| | Azure Content Understanding | Mistral Document AI |
|---|---|---|
| **HTML input** | Entire document = **1 page** (no native page concept) | N/A — doesn't accept HTML |
| **PDF input** | Each PDF page = 1 page | Each PDF page = 1 page |
| **Image input** | 1 image = 1 image (separate pricing tier) | 1 image = 1 page |

> **Key insight:** CU bills a long HTML article as **1 page** regardless of content length ([source](https://learn.microsoft.com/azure/ai-services/content-understanding/document/elements#document-elements): *"For file formats like HTML or Word documents, which lack a native page concept without rendering, the entire main content is treated as a single page."*). Mistral, which processes the **PDF-rendered** version, bills per rendered page — a typical KB article renders to roughly **3–5 PDF pages** via Playwright.
>
> This means CU's content extraction has a structural advantage for long HTML documents: 1 page flat-rate vs N pages in the Mistral pipeline. But Mistral's per-page rate ($0.002) is much lower than CU's ($0.005), so the difference is modest.

### Pricing Inputs (GPT-4.1 Global Deployment, East US)

| Rate Card | Price |
|---|---|
| CU content extraction (documents) | $5.00 / 1,000 pages |
| CU content extraction (images) | $0.00 (no charge) |
| CU contextualization | $1.00 / 1M tokens (~1,000 tokens/page or image) |
| CU figure analysis | ~1,000 input + 200 output tokens per figure |
| CU image analyzer fields | ~1,000 input + 300 output tokens per image (est.) |
| GPT-4.1 input tokens | $2.00 / 1M tokens |
| GPT-4.1 output tokens | $8.00 / 1M tokens |
| Mistral OCR (standard) | $2.00 / 1,000 pages ($0.002/page) |
| Mistral OCR (batch) | $1.00 / 1,000 pages ($0.001/page) |

> Sources: [CU pricing explainer](https://learn.microsoft.com/azure/ai-services/content-understanding/pricing-explainer), [Azure OpenAI pricing](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/). All prices are illustrative and subject to change.

### Per Article Breakdown (1 article, 3 images, ~5 rendered PDF pages)

#### CU Pipeline

Our pipeline makes **1 + N** CU calls: `prebuilt-documentSearch` for text (which includes built-in figure analysis), plus `kb-image-analyzer` for each image.

| Component | Calculation | Cost |
|---|---|---|
| **documentSearch — content extraction** | 1 page × $5.00/1,000 | $0.0050 |
| **documentSearch — contextualization** | 1,000 tokens × $1.00/1M | $0.0010 |
| **documentSearch — figure analysis (input)** | 3 figs × 1,000 tokens × $2.00/1M | $0.0060 |
| **documentSearch — figure analysis (output)** | 3 figs × 200 tokens × $8.00/1M | $0.0048 |
| **kb-image-analyzer — content extraction** | 3 images, no charge | $0.0000 |
| **kb-image-analyzer — contextualization** | 3 × 1,000 tokens × $1.00/1M | $0.0030 |
| **kb-image-analyzer — field extraction (input)** | 3 × 1,000 tokens × $2.00/1M | $0.0060 |
| **kb-image-analyzer — field extraction (output)** | 3 × 300 tokens × $8.00/1M | $0.0072 |
| **CU Total** | | **~$0.033** |

#### Mistral + GPT-4.1 Pipeline

| Component | Calculation | Cost |
|---|---|---|
| **PDF rendering (Playwright)** | Compute only | $0.0000 |
| **Mistral OCR** | 5 PDF pages × $2.00/1,000 | $0.0100 |
| **GPT-4.1 image descriptions (input)** | 3 images × ~1,500 tokens × $2.00/1M | $0.0090 |
| **GPT-4.1 image descriptions (output)** | 3 images × ~300 tokens × $8.00/1M | $0.0072 |
| **Mistral + GPT-4.1 Total** | | **~$0.026** |

### At Scale

| Scale | CU Pipeline | Mistral + GPT-4.1 | Mistral + GPT-4.1 (batch OCR) |
|---|---|---|---|
| 1 article | ~$0.033 | ~$0.026 | ~$0.021 |
| 100 articles | ~$3.30 | ~$2.60 | ~$2.10 |
| 1,000 articles | ~$33 | ~$26 | ~$21 |

### Cost Analysis Notes

1. **Costs are comparable** — In the per-article range, both pipelines cost ~$0.02–0.04. Neither has a dramatic advantage.
2. **CU's main cost drivers** are figure analysis tokens and image analyzer tokens (GPT-4.1 charges via Foundry deployment), not the CU content extraction per-page fee itself.
3. **Mistral's main cost driver** is also the GPT-4.1 image description calls. Mistral OCR's own fee is negligible at $0.002/page.
4. **Both pipelines pay GPT-4.1 for image understanding** — CU uses it internally for figure analysis and custom field extraction; Mistral pipeline calls it directly. The token costs are similar.
5. **Page-count sensitivity** — If an article renders to >5 PDF pages, Mistral's OCR cost rises proportionally, while CU stays flat. For articles rendering to 10+ pages, CU's extraction cost advantage grows, but the GPT-4.1 image costs (which are page-count independent) still dominate.
6. **Batch discount** — Mistral offers 50% off for batch processing ($1/1,000 pages), which could matter for bulk KB ingestion.

---

## 7. Can Mistral Process HTML with Embedded Images Directly?

**Short answer: No.**

Mistral Document AI / OCR 3 does **not** accept HTML as input. Supported input formats are:
- **PDF** (primary document format)
- **Images** (PNG, JPEG, AVIF, etc.)
- **DOCX, PPTX** (office documents)

### Implications

We cannot feed our raw HTML files (even with base64-embedded images) to Mistral. The two viable approaches are:

1. **HTML → PDF → Mistral OCR** (recommended — preserves images inline in the rendered PDF)
2. **Python HTML parser for text + Mistral/LLM for images** (alternative — avoids PDF step but loses Mistral's OCR advantage for text)

Option 1 is preferred because:
- Mistral OCR excels at PDF processing and will extract the rendered images automatically
- Hyperlinks survive in the PDF rendering and are extracted by Mistral
- Tables rendered by the browser are captured faithfully
- We get a single API call for the entire document's text + image positions

The **two-step approach** (text separately, images separately) would only make sense if we wanted to avoid the Playwright/PDF dependency entirely — but that was our architecture before (Option 1 in `004-architecture-proposal.md`), and CU handles HTML text extraction better than a Python library in that scenario.

---

## 8. Open Questions for Spike

If we proceed with a spike to evaluate Mistral Document AI, the following questions need empirical testing:

1. **PDF image extraction quality** — When Mistral extracts images from a PDF rendered from our HTML, what quality are the base64 images vs the original source PNGs? Is there noticeable quality loss from the PDF rendering step?

2. **Image-to-source mapping** — Does the HTML marker injection strategy (§5a) work reliably? Does Mistral OCR faithfully read the injected marker text from the rendered PDF? Are markers correctly positioned adjacent to each image placeholder in the output markdown?

3. **Hyperlink fidelity** — Do hyperlinks from the original HTML survive the Playwright rendering and get extracted by Mistral? (CU failed at this from HTML input but succeeded from PDF.)

4. **Azure endpoint limitations** — The Azure deployment limits to 30 pages / 30MB. Are our articles within these limits? (Our current articles are single-page HTML, so this should be fine.)

5. **Markdown quality comparison** — Side-by-side comparison of Mistral OCR markdown vs CU `prebuilt-documentSearch` markdown for the same rendered PDF. Which produces better structure, heading hierarchy, table formatting?

6. **LLM image description quality** — Using GPT-4.1 directly for image descriptions vs CU's custom `kb-image-analyzer` — is quality comparable? Can we replicate the `Description`, `UIElements`, `NavigationPath` schema?

7. **Azure API compatibility** — Does the Azure-deployed `mistral-document-ai-2512` support all features (table_format, extract_header, include_image_base64) or is it a subset?

8. **End-to-end latency** — Playwright render + Mistral OCR + N×GPT-4.1 image calls vs CU HTML + N×CU image calls. Which is faster?

---

## 9. Recommendation

### Verdict: Worth Spiking, Not a Clear Win

Mistral Document AI is a strong OCR model with excellent PDF→markdown capabilities, competitive pricing, and clean image extraction. However, for our specific pipeline:

- **It reintroduces the Playwright/PDF dependency** we specifically eliminated in ARD-001
- **It lacks native HTML support**, which CU provides
- **It doesn't generate image descriptions** — we'd need GPT-4.1 vision calls, adding a dependency
- ~~Summary not generated~~ — not actually needed; `fn-index` never uses it

The most compelling reason to explore it would be:
1. **Better image extraction from PDFs** — Mistral returns clean base64 images vs CU's bounding polygon approach that requires PyMuPDF cropping
2. **Hyperlink extraction from PDFs** — if Mistral reliably extracts hyperlinks from the rendered PDF, it solves a gap we had with CU on HTML
3. **Pricing transparency** — $2/1,000 pages is simple and potentially cheaper than CU
4. **Multi-cloud flexibility** — available on Azure, Mistral platform, and self-hosted

### Suggested Next Step

Run a focused spike comparing the same KB article processed through both pipelines:
1. **Current:** HTML → CU (text) + images → CU (descriptions) → merged MD
2. **Proposed:** HTML → PDF (Playwright) → Mistral OCR → image mapping via markers → GPT-4.1 (descriptions) → merged MD

Compare: markdown quality, image mapping accuracy, hyperlink preservation, end-to-end latency, and cost.

---

## References

- [Mistral OCR 3 announcement](https://mistral.ai/news/mistral-ocr-3)
- [Mistral Document AI docs](https://docs.mistral.ai/capabilities/document_ai/basic_ocr)
- [Mistral OCR 3 model card](https://docs.mistral.ai/models/ocr-3-25-12)
- [Azure Foundry — Mistral models sold directly by Azure](https://learn.microsoft.com/azure/ai-foundry/foundry-models/concepts/models-sold-directly-by-azure?view=foundry-classic&pivots=azure-direct-others)
- [Azure — How to use image-to-text models](https://learn.microsoft.com/azure/ai-foundry/how-to/use-image-models?view=foundry-classic)
- [Azure — Choosing the right tool for document processing](https://learn.microsoft.com/azure/ai-services/content-understanding/choosing-right-ai-tool)
- [Mistral model deprecation — OCR 2503 → Document AI 2505/2512](https://learn.microsoft.com/azure/ai-foundry/concepts/model-lifecycle-retirement?view=foundry-classic)
- [Our CU research — architecture-proposal.md](004-architecture-proposal.md)
- [Our CU research — architecture-research.md](002-architecture-research.md)
- [Our CU research — analyzer-options.md](001-analyzer-options.md)
