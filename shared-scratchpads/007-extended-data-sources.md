# Scratchpad: Extended Data Sources Support — Research & Proposal Planning

## Planner — Research Findings (2026-03-19 14:00)

### Current State

- **KB structure:** `kb/staging/{department}/{article-id}/` → `fn-convert` → `kb/serving/{article-id}/` (flat, with `metadata.json`)
- **Existing department:** `engineering` with 3 Azure HTML articles (agentic-retrieval, content-understanding, search-security)
- **Serving contract:** `article.md` + `images/` + `metadata.json` per article
- **Index schema:** `kb-articles` with fields: id, article_id, chunk_index, content, content_vector, image_urls, source_url, title, section_header, department, key_topics
- **Converters:** Three backends (CU, Mistral, MarkItDown), all produce identical output. MarkItDown already supports HTML, PDF, DOCX, PPTX natively.
- **MarkItDown capabilities (key for this effort):** HTML, PDF, DOCX, XLSX, PPTX, images, audio (via speech-to-text), ZIP files
- **Mistral Doc AI capabilities:** PDF, images (PNG/JPEG), PPTX, DOCX — NOT HTML
- **Vision middleware:** Injects base64 images into LLM conversation for visual reasoning
- **Department filtering:** Already implemented via Epic 011 (OData filter on `department` field)

### Key Architecture Insight

The pipeline's serving layer is already a contract boundary — `fn-index` doesn't care what generated the content. This means:
- New file types only require changes to `fn-convert` (or new converter variants)
- `fn-index` stays untouched as long as the serving format is respected
- The serving format CAN be extended (new artifact folders) without breaking existing indexing

### Company Theme Decision: "Contoso Robotics"

**Rationale:** A collaborative robotics (cobot) company provides:
- Rich visual content (architecture diagrams, schematics, hardware photos) — great for image injection demos
- Natural cross-department overlap (Engineering designs it, Marketing sells it, Support helps customers use it)
- Plausible diversity of document types across all 3 departments
- Strong demo storyline: "Ask the AI about your cobot" spans product specs, troubleshooting, and sales materials
- Good public content availability: ROS 2 docs, open-source robotics projects, Creative Commons hardware designs

**Company narrative:** Contoso Robotics makes the "CoBot Pro" line of collaborative industrial robots. The three departments are:
1. **Support** — Customer-facing documentation: installation guides, troubleshooting, configuration, maintenance
2. **Marketing** — Go-to-market materials: product launches, analyst briefings, customer success stories, podcasts
3. **Engineering** — Technical specs: software architecture, hardware schematics, sensor integration, ROS 2 design docs

### Sourcing Strategy

| Department | File Types | Source Strategy |
|------------|-----------|----------------|
| Support (20 docs) | HTML + images | Adapt from public ROS 2 documentation, Universal Robots knowledge base, or industrial robotics safety standards. Restructure content to fit "Contoso Robotics CoBot Pro" branding. |
| Marketing (~10 docs) | PDF, PPTX, audio (MP3/WAV), video (MP4 reference), infographic (PDF) | **Create synthetic content** — generate realistic but fictional materials using free tools. PPTX with robotics imagery, PDF brochures, audio from TTS of scripted interviews, video references to public robotics demos. |
| Engineering (~10 docs) | PDF (technical specs), HTML (API docs), images (schematics/diagrams) | Mix of adapted open-source hardware docs (e.g., OpenManipulator, ROS 2 design docs) and created architecture diagrams. |

### Phase Design

**Phase 1 — "HTML + PDF Foundation"**: Add 3 departments with primarily text-based content. Extend convert to handle PDF. ~30+ documents total. Proves multi-department, multi-format pipeline.

**Phase 2 — "Rich Office Docs"**: Add PPTX, DOCX processing. Extract images from these formats. Extend serving format with `originals/` for source file references. ~40+ documents total.

**Phase 3 — "Audio/Video & Deep Media"**: Add audio transcription, video reference links. Extend index with media metadata. Deep audio transcripts with emotion/tone markers. ~45+ documents total.

### Architecture Changes Needed

1. **fn-convert generalization**: Currently HTML-specialized. Needs a dispatcher that routes by file extension to appropriate converter (MarkItDown handles most natively).
2. **Serving format extension**: Add `originals/` folder for source files, `media/` folder for transcription artifacts. Extend `metadata.json` with `source_type`, `original_file`, `media_refs[]`.
3. **Index schema evolution**: Add `source_type` (filterable), `original_file_url`, `media_urls` (collection). Extend image_urls concept to all artifact types.
4. **Web UI enhancements**: Display/link to original documents (PDF viewer, PPTX download), audio player with timestamp navigation, video embeds.
5. **Vision middleware scope**: Inject images from any source (PDF, PPTX), not just HTML-sourced images. Already works if images end up in `images/` folder — the key is ensuring converters extract them.

### Decisions

- User confirmed: Support department does NOT need to be Azure docs — unified theme is more valuable
- Existing `engineering` department content (3 Azure articles) will be replaced, not moved to `support`
- All departments should have interconnected content for cross-department Q&A demo scenarios
- Audio injection into LLM: NOT worth it — transcript carries the value; reference the audio for UI playback
- Video injection into LLM: NOT worth it — use as reference links only
- Image injection from PDFs/PPTX: YES — same pipeline as HTML images, very valuable for engineering diagrams

## Planner — Plan Complete (2026-03-19 14:30)

- Decision: "Contoso Robotics" as unified company theme — best visual storytelling + content availability
- Decision: 3 phases (HTML+PDF → Office docs → Audio/Video) — each phase is independently useful
- Decision: MarkItDown is the primary converter for new file types (already supports PDF, PPTX, DOCX, audio)
- Decision: Create synthetic marketing content rather than source it (most realistic for demo)
- Decision: Research doc should be comprehensive enough to directly inform an Epic
- Rejected: Azure docs for support department — too limiting for unified theme
- Rejected: Injecting audio/video into LLM prompts — transcript + reference links are sufficient
- Constraint: fn-index should remain unchanged in Phase 1; serving format extensions happen in Phase 2+
- Constraint: Existing index schema additions must be backward-compatible

## Implementer — Research Document Complete (2026-03-19 15:00)

### Completed

- Created `docs/research/007-extended-data-sources-support.md` (679 lines)
- Includes all sections from the plan: Context & Motivation, Company Theme, Department Definitions (42 documents cataloged), Content Sourcing Strategy, Serving Format Evolution (3 phases), Architecture Changes (6 subsections), Three-Phase Roadmap with Mermaid gantt, 5 Demo Scenarios, Open Questions & Risks
- Appendix A: Cross-reference map between documents (10 cross-department links)
- Appendix B: MarkItDown format support detail for each target format

### Key decisions made in the doc

- Extend `fn_convert_markitdown` rather than creating new converter packages — MarkItDown handles PDF/PPTX/DOCX/audio natively
- Vision middleware needs NO changes — images from any source land in `images/` and flow through existing pipeline
- Phase 1 minimum viable: 14 docs (8 Support HTML + 3 Marketing PDF + 3 Engineering PDF)
- Full Phase 1: 32 docs (20 Support HTML + 6 Marketing PDF + 6 Engineering PDF)
- PDF image extraction needs a spike — MarkItDown text extraction is validated but embedded image extraction quality is unknown

### Handoff (Rev 1)

- Document is ready for review and discussion
- No code changes were made — this is purely a research/proposal document
- Next step after approval: Create Epic 012 from this research, starting with a PDF conversion spike

## Implementer — Rev 2 Revisions (2026-03-19 16:00)

### User Feedback Applied

1. **Serving folder structure: `originals/` + `derived/`** — Replaced confusing `images/` + `originals/` + `media/` trichotomy with a cleaner two-folder model. Rule: originals are inputs, derived are outputs. A podcast MP3 goes in `originals/`; extracted images go in `derived/images/`; a VTT transcript goes in `derived/`. No ambiguity.
2. **Audio transcription: LLM-based** — Replaced Azure Speech Services dependency with Whisper (Azure OpenAI deployment) + GPT-4o audio evaluation. No new infra needed. Diarization via LLM post-processing.
3. **`source_type` always required** — No default fallback. `fn-convert` must always write `source_type` to `metadata.json`. Existing Azure articles are fully replaced, no legacy to accommodate. Also useful for faceting in UI.
4. **Converter supported formats (no dispatcher)** — Each converter declares `SUPPORTED_FORMATS`. CU and Mistral stay HTML-only. MarkItDown handles all formats. Unsupported format → skip + WARNING. Same loop logic, no central dispatcher.
5. **Removed multi-agent section** — Dropped section 6.6 about department-specific agents. Out of scope for this proposal.
6. **Added persona switcher UI** — 3-option toggle (Alex/Support, Jordan/Marketing, Casey/Engineering) in Chainlit. Sends department filter to agent. Same question, different persona → different results. Integrates with existing Epic 011 contextual filtering in dev mode.
7. **Reduced doc count** — 42 → ~26 documents. Focused on fewer, higher-quality docs with deliberate cross-references.
8. **Simplified product line** — 5 products → 3 (CoBot Pro + Vision Module + Safety Controller). One core robot, not three models. Reduces content creation scope.
9. **Cross-references in doc tables** — Every document now shows which other department docs it references. 14 cross-references mapped in Appendix A.

### Document stats

- Rev 2: 748 lines (up from 679 — more detail in serving structure and persona switcher sections)
- 26 documents across 3 departments (10 Support + 8 Marketing + 8 Engineering)
- Minimum viable: 10 documents (5 Support + 2 Marketing + 3 Engineering)
- 14 cross-department references mapped

### Handoff (Rev 2)

- Document ready for second review
- Key decision points for user: Phase 1 scope (full 20 docs vs. minimum 10), `images/` migration timing (Phase 1 or Phase 2)

## Implementer — Rev 3 Revisions (2026-03-19 17:00)

### User Feedback Applied

1. **No backward compatibility anywhere** — We are rebuilding all sources from scratch. Removed all migration discussion, backward-compat bullets, and phased `images/` → `derived/images/` migration. The `originals/` + `derived/` structure is adopted from day one.

2. **Three clean phases redefined:**
   - **Phase 1 — Core Document Types:** HTML, PDF, PPTX, DOCX. Full `originals/` + `derived/images/` structure from the start. ~24 documents across 3 departments. Persona switcher + View Original UI.
   - **Phase 2 — Audio:** MP3 podcast transcription via Whisper/LLM. Adds `derived/transcript.vtt`. HTML5 audio player with seek.
   - **Phase 3 — Video:** Video key frame extraction + transcript. Key frames flow through vision middleware via `image_urls`. Embedded video player with seek.

3. **Rethought index schema — clean separation of concerns:**
   - **`image_urls`** (Collection, existing) — Images are special: they're the only thing injected into the LLM by vision middleware. Many per chunk. Source-agnostic (HTML, PDF, PPTX, video key frames all produce images in `derived/images/`).
   - **`source_type`** (String, Phase 1) — Required, filterable. Document format (html, pdf, pptx, docx, audio, video).
   - **`original_file_url`** (String, Phase 1) — Single URL to the source document in `originals/`. Used for "View Original" (PDF/PPTX), "Play" (audio), "Watch" (video). One per article.
   - **`original_timestamp`** (String, Phase 2) — Seek position for audio/video chunks (e.g., "07:32"). Null for non-media. One per chunk.
   - **Dropped `media_urls` (collection) and `media_timestamps` (JSON string)** — A chunk relates to at most one audio/video file. `original_file_url` + `original_timestamp` cover all cases cleanly.

4. **Vision middleware update** — Only change: image path from `images/` to `derived/images/`. Logic unchanged.

5. **UI enhancements brought forward** — "View Original" and PDF.js viewer moved to Phase 1 (since `original_file_url` is now a Phase 1 field).

### Document stats

- Rev 3: ~750 lines
- Phase 1 scope: ~24 docs (10 Support HTML + 6 Marketing PDF/PPTX + 8 Engineering PDF/HTML)
- Minimum viable Phase 1: 11 docs (5 Support + 3 Marketing + 3 Engineering)
- Index: 4 new fields total across all phases (source_type, original_file_url in P1; original_timestamp in P2)

### Handoff (Rev 3)

- Document ready for review
- All backward compatibility concerns removed — clean slate approach
- Index schema is now clean: images (collection, LLM-injected) + original file (single, UI reference) + timestamp (single, audio/video seek)

## Implementer — Rev 4 Revisions (2026-03-19 18:00)

### User Feedback Applied

1. **Terminology rename: `article` → `document`** — With the KB expanding to PDFs, PPTXs, audio, and video, "article" is too narrow. A podcast MP3 is a "document" in the KB. Full rename proposed across every layer:
   - `article.md` → `document.md`
   - `article-id` → `document-id` (paths)
   - `article_id` → `document_id` (code + index field)
   - `kb-articles` → `kb-documents` (index name)
   - `list_articles()` → `list_documents()`, `download_article()` → `download_document()`, etc.
   - `chunk_article()` → `chunk_document()`
   - `/api/images/{article_id}/` → `/api/images/{document_id}/`

2. **New Section 6.1** — Dedicated section documenting the full rename scope with old→new mapping table and affected files inventory. All subsequent sections renumbered (6.2→6.3, etc.).

3. **Index schema updated** — `document_id` field added to table in Section 6.5. Index rename `kb-articles` → `kb-documents` documented.

4. **Phase 1 roadmap updated** — Rename added as explicit scope item in Phase 1. Definition of Done includes rename completion.

5. **All structural references updated** — Every `serving/{article-id}/`, `article.md`, code snippet in the doc now uses `document` terminology.

### Document stats

- Rev 4: ~790 lines (added Section 6.1 rename table)
- Prose: All "article" references replaced with "document" except in Section 6.1 rename table (deliberately shows old→new) and external URLs

### Handoff (Rev 4)

- Document ready for review
- Rename is a Phase 1 task — no migration needed since we're rebuilding all content from scratch

## Implementer — Rev 5 Revisions (2026-03-19 19:00)

### User Feedback Applied

1. **Persona rename: Alex → Sam** — Support persona renamed to "Sam (Support)" to avoid name collision.

2. **`originals/` → `original/` (singular)** — Each document has exactly one original source, so the folder is singular. `original/` contains the complete source document and all its constituent files.

3. **HTML original handling** — For HTML sources, `original/` contains the full HTML document AND all its images/assets (everything from staging). Images are **copied** into `derived/images/` so the pipeline always reads from one consistent location. `original/` stays intact as the complete source reference.

4. **Simplified metadata field: `original_file` → `original`** — The metadata field is now just `"original": "index.html"` — the filename of the primary source within `original/`. Code knows the folder structure, so no path prefix needed.

5. **Index field: `original_file_url` → `original_url`** — Shorter, cleaner. Constructed by indexer from `{document-id}/original/{metadata.original}`.

6. **Updated all serving format diagrams** — Phase 1 now shows two examples (HTML with images + PDF), making the HTML image copy pattern explicit.

### Handoff (Rev 5)

- Document ready for review
- Key clarification: `original/` = complete source copy, `derived/` = pipeline outputs. Pipeline never reads from `original/` — only from `derived/`.

---

## Implementer — Epic Creation (2026-03-19 18:00)

### Epics Created

Created 3 execution epics from the research proposal:

1. **Epic 012 — Contoso Robotics Content Creation** (`docs/epics/012-contoso-robotics-content-creation.md`)
   - 5 stories: content outlines, Support HTML (10 docs), Marketing PDF/PPTX (6 docs), Engineering PDF/HTML (8 docs), retire old content + validate
   - ~24 documents total, all with cross-references and 2–3 images each
   - Can proceed in parallel with Epic 013

2. **Epic 013 — PDF/PPTX Conversion Quality Spike** (`docs/epics/013-pdf-pptx-conversion-spike.md`)
   - 3 stories: PDF conversion + image extraction, PPTX conversion + speaker notes, spike documentation
   - Tests MarkItDown vs. PyMuPDF for image extraction quality
   - Confirms speaker notes inclusion — if missing, prototypes `python-pptx` extraction
   - Output: `docs/spikes/004-pdf-pptx-conversion.md` with go/no-go recommendation
   - Can proceed in parallel with Epic 012

3. **Epic 014 — Extended Data Sources: Phase 1** (`docs/epics/014-extended-data-sources-phase1.md`)
   - 9 stories: terminology rename, serving format, converter multi-format, index schema, vision middleware, persona switcher, source badge + View Original, integration testing, documentation
   - Depends on both Epic 012 (content) and Epic 013 (spike findings)
   - Persona switcher uses Chainlit `cl.ChatSettings` with `Select` widget — no separate spike needed (user confirmed)
   - Department flows via `extra_body` from web-app to agent middleware

### Key Decisions

- **No separate persona switcher spike** — user said "no need to spike on toggle, I'm sure we can find a way by just reading docs." Epic 014 Story 6 includes inline research notes on Chainlit `ChatSettings` approach.
- **Epic 014 depends on both 012 and 013** — content must exist and spike must validate conversion quality before full implementation.
- **Research doc Next Steps updated** — Section 10 now references all three epics with links and execution order.

### Handoff

- 3 epic files created in `docs/epics/`
- Research doc `docs/research/007-extended-data-sources-support.md` Next Steps section updated with epic links
- Ready for user review

---

## Reviewer — Epic Review (2026-03-19 19:00)

### Scope

Reviewed all 3 epic files against Research 007 and existing epic format conventions.

### Critical Issues

1. **Epic 012 circular dependency on Epic 014** — Success Criteria lines 7-8 and Story 5 DoD assume `make convert` and `make index` work for all 24 docs. But 12 of those are PDF/PPTX — converter can't handle them until Epic 014 Story 3. Either scope pipeline validation to HTML-only docs, or note that full pipeline validation requires Epic 014.

### Warnings

1. **Epic 014 Story 6 dependency is misleading** — Persona switcher dependency on "Story 4 (index must have department field)" is wrong — the `department` field already exists from Epic 011. The persona switcher just needs content indexed, not new index fields. True dependency is Epic 012 (content) + existing department field.
2. **PDF.js inline viewer missing from Epic 014** — Research 007 Section 6.8 lists "PDF inline viewer" (PDF.js for in-browser viewing from citation panel) as a Phase 1 Web UI enhancement. Not mentioned in Epic 014 Story 7 or anywhere else.
3. **Epic 014 Story 1 DoD `grep` check too broad** — `grep -ri "article" src/` will match English words in comments, docstrings, error messages that legitimately use "article." Should target specific patterns: `article_id`, `kb-articles`, `list_articles`, `article.md`, etc.

### Suggestions

1. **No DOCX documents in corpus** — Phase 1 pipeline supports DOCX but no actual documents use it. Consider adding at least one DOCX document (e.g., a Marketing whitepaper or an Engineering design doc) to validate the full format matrix. Low effort, high validation value.
2. **Epic 014 dependency granularity** — The "Depends On" table says Epic 012 is required, but Stories 1-2 (rename + serving format) don't need new content. They work with existing 3 docs. Only Story 3+ truly needs Epic 012. More granular deps would enable earlier parallel work.

### What's Good

- Document counts match Research 007 Phase 1 scope exactly (10+6+8=24, MP3 podcasts correctly deferred to Phase 2)
- Epic 014 Story 1 deliverables match the Section 6.1 rename mapping table precisely
- Epic 013 correctly identifies the two key open questions (PDF image extraction, PPTX speaker notes) and structures parallel stories
- Cross-epic execution order is well-defined: 012+013 parallel → 014 sequential
- Persona names (Sam/Jordan/Casey) and ChatSettings approach correctly carried from research doc
- Index schema changes match Section 6.5 exactly — `original_timestamp` correctly deferred to Phase 2
- All epics follow the project's epic template format consistently

---

## Reviewer — Post-Fix Review (2026-03-19 20:00)

### Scope

Reviewed all 4 fixes applied by the Implementer against the original review findings. Verified each fix addresses the specific issue raised.

### Fix Verification

1. **Epic 012 circular dependency — FIXED** ✅
   - Success Criteria lines 7-8 now scoped to "HTML documents" with parenthetical "(PDF/PPTX require Epic 014 multi-format support)"
   - Story 5 deliverables updated: pipeline validation scoped to "HTML documents (12 HTML across Support + Engineering)"
   - Story 5 adds explicit note: "Full-corpus pipeline validation (including PDF/PPTX) is deferred to Epic 014 Story 8"
   - Story 5 DoD updated: operations scoped to HTML, PDF/PPTX called out as "exist in staging and are structurally valid, but pipeline validation requires Epic 014"
   - Query validation scoped to "(HTML docs only)" / "(using HTML docs)"

2. **Epic 014 Story 6 dependency — FIXED** ✅
   - Changed from "Story 4 (index must have department field)" to "Epic 012 (content must be indexed); Epic 011 (department field + SecurityFilterMiddleware already exist)"
   - Correctly identifies both real dependencies: content to search against, and the existing infra from Epic 011

3. **PDF.js inline viewer — FIXED** ✅
   - Added as deliverable in Story 7: "PDF inline viewer — embed PDF.js for in-browser viewing from the citation panel (renders PDF without requiring download)"
   - Placed after "View Original" button deliverable, which is the natural position

4. **Epic 014 Story 1 grep check — FIXED** ✅
   - Changed from `grep -ri "article" src/` to `grep -rE "article_id|article_dir|article_title|kb-articles|list_articles|download_article|upload_article|chunk_article|article\.md" src/`
   - Targets all code-specific patterns from the Research 007 Section 6.1 rename table
   - No false positives from legitimate English "article" usage

### Remaining Suggestions (unchanged — not addressed, not required)

- No DOCX in the corpus — pipeline supports it but no doc validates it
- Epic 014 dependency granularity — Stories 1-2 could start before Epic 012

These are nice-to-haves. Neither blocks execution.

### Verdict

All 4 critical issues and warnings are resolved correctly. No new issues introduced by the fixes. Tests pass (123 passed, 2 pre-existing Playwright failures unrelated to these changes).

IMPLEMENTATION COMPLETE

---

## Reviewer — Final Review (2026-03-19 21:00)

### Scope

Full review of all 3 epic files (012, 013, 014), the Research 007 Next Steps update, and the scratchpad. Checked architecture compliance, security posture of planned changes, epic doc quality, cross-epic dependency correctness, and alignment with Research 007.

### Critical Issues

None.

### Warnings

1. **Epic 012 Story 5 references "Marketing podcast reference"** — [012-contoso-robotics-content-creation.md](docs/epics/012-contoso-robotics-content-creation.md#L214): search query validation mentions `"force-torque sensor" → results from Engineering spec + Support troubleshooting + Marketing podcast reference`. Podcasts (MP3) are deferred to Phase 2 — they are listed in Research 007's Marketing table (#7, #8) but excluded from Epic 012 Story 3 (which has 6 docs: 4 PDF + 1 PPTX + 1 DOCX). Story 5 search queries should reference existing Marketing docs only. Suggested fix: change "Marketing podcast reference" to "Marketing technical brief" or "Marketing competitive analysis" — both exist in Epic 012 Story 3 and contain force-torque content.

### Suggestions

1. **Epic 012 document count: 10+6+8=24, not "~24"** — The "~" prefix suggests uncertainty, but the exact scope is defined (10 HTML + 4 PDF + 1 PPTX + 1 DOCX + 6 PDF + 2 HTML = 24). Minor — the "~" doesn't cause harm but "24" would be more precise.
2. **Prior suggestions still open (accepted risk)**:
   - No DOCX in corpus (DOCX pipeline untested). Epic 012 Story 3 now includes a DOCX (Meridian case study) — this is actually resolved. The previous reviewer note is stale.
   - Epic 014 dependency granularity (Stories 1-2 can start before Epic 012) — valid but low impact since 012+013 are short execution.

### Architecture Compliance

- [x] No cross-service imports — epics correctly scope changes to their respective services
- [x] Shared code (`detect_source_type()`) placed in `src/functions/shared/` — correct location per architecture
- [x] Config via environment variables — no hardcoded values planned
- [x] `DefaultAzureCredential` for all Azure access — no new auth patterns introduced
- [x] File placement follows service conventions (converters in `fn_convert_*`, agent changes in `src/agent/`, web-app in `src/web-app/`)

### Security Review

- [x] No secrets, connection strings, API keys, or tokens in any epic doc
- [x] `original_url` construction in indexer uses `f"{document_id}/original/{metadata['original']}"` — review at implementation time that `metadata['original']` is sanitized to prevent path traversal (e.g., `../../sensitive-file`)
- [x] New `/api/originals/{document_id}/{filename}` proxy route (Story 7) must validate both `document_id` and `filename` params against path traversal — flag at implementation review
- [x] Persona switcher sends department via `extra_body` — no auth bypass; `REQUIRE_AUTH=false` dev-mode only
- [x] Managed identity used for all service access — no new credential patterns

### Epic Doc Quality

- [x] All 3 epics follow project template format (Status, Created, Updated, Objective, Success Criteria, Background, Stories with Deliverables + DoD)
- [x] Story dependencies form valid DAGs — no circular dependencies
- [x] Each story has testable Definition of Done criteria
- [x] Research 007 Next Steps section correctly links all 3 epics with execution order

### Cross-Epic Dependencies

- [x] Epic 012 + 013 can proceed in parallel — no interdependency
- [x] Epic 014 depends on both 012 and 013 — correctly documented in the Depends On table
- [x] Epic 012 Story 5 pipeline validation correctly scoped to HTML-only (PDF/PPTX deferred to Epic 014 Story 8)
- [x] Epic 014 Story 6 dependency correctly references Epic 012 + Epic 011 (not Story 4)
- [x] Epic 014 Story 3 correctly depends on Epic 013 spike results

### What's Good

- Clean three-epic decomposition: content creation (012), spike/validation (013), and implementation (014) are well-separated concerns
- Epic 013 correctly structures PDF and PPTX investigation as parallel stories — enables fastest de-risking
- Epic 014 story ordering creates a natural implementation flow: rename → format → converter → index → vision → UI → integration → docs
- The "View Original" proxy approach (option 1) in Story 7 is architecturally consistent with the existing image proxy pattern
- DOCX presence in corpus (Meridian case study) — resolves the "no DOCX validation" concern from the previous review
- PDF.js inline viewer correctly added to Story 7 per Research 007 Section 6.8

### Verdict

**⚠️ Approve with comments** — 1 warning must be addressed (stale podcast cross-reference in Story 5). All other aspects are clean. No rework or re-plan needed.

### Handoff Recommendation

**Quick Fix** — replace "Marketing podcast reference" with a valid Phase 1 Marketing document reference in Epic 012 Story 5 line 214.

---

## Implementer — Warning Fix (2026-03-19 21:30)

- Fixed W1: Changed "Marketing podcast reference" → "Marketing competitive analysis" in Epic 012 Story 5 search query validation (line 214). The Competitive Landscape Analysis doc exists in Story 3 and contains force-torque sensor comparisons.
- Tests: 131 agent passed, 174 functions passed, 123 web-app passed (2 pre-existing Playwright failures)

---

## Reviewer — Post-Fix Approval (2026-03-19 21:30)

- Verified: `docs/epics/012-contoso-robotics-content-creation.md` line 214 now reads "Marketing competitive analysis" — correct, this doc exists in Story 3 and references force-torque sensor content
- Tests pass
- Verdict: ✅ Approve

════════════════════
  IMPLEMENTATION COMPLETE
════════════════════
