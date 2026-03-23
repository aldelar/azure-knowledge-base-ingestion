#!/usr/bin/env python3
"""Download real-world public domain documents for conversion quality testing.

These documents stress-test the conversion pipeline with real complexity:
multi-column layouts, real photographs/diagrams, extensive hyperlinks,
cross-page tables, and diverse formatting.

Usage:
    python download_real_world.py

Documents are saved to samples/real-world/.

Note: Some URLs may require direct internet access. If downloads fail in a
sandboxed environment, run this script locally and commit the files.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parent / "samples" / "real-world"

# Each entry: (filename, url, description, format, complexity notes)
DOCUMENTS = [
    # --- PDF ---
    (
        "owasp-asvs-4.0.3.pdf",
        "https://github.com/OWASP/ASVS/raw/master/4.0/"
        "OWASP%20Application%20Security%20Verification%20Standard%204.0.3-en.pdf",
        "OWASP Application Security Verification Standard 4.0.3",
        "PDF",
        "71 pages, complex tables (security controls matrix), "
        "extensive hyperlinks (377), 73 embedded images, "
        "multi-level headings, bullet lists, cross-references",
    ),
    (
        "nist-csf-2.0.pdf",
        "https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf",
        "NIST Cybersecurity Framework 2.0",
        "PDF",
        "Government whitepaper with diagrams, tables, 103 hyperlinks, "
        "13 images, multi-column layout, cross-references, appendices",
    ),
    (
        "arxiv-attention.pdf",
        "https://arxiv.org/pdf/1706.03762v5",
        "Attention Is All You Need (Vaswani et al.)",
        "PDF",
        "Seminal ML paper with mathematical equations, 3 figures, "
        "113 hyperlinks, 2-column layout, bibliography references",
    ),
    # --- PPTX ---
    (
        "apache-poi-SampleShow.pptx",
        "https://svn.apache.org/repos/asf/poi/trunk/test-data/slideshow/"
        "SampleShow.pptx",
        "Apache POI: SampleShow (2 slides with speaker notes)",
        "PPTX",
        "2 slides with speaker notes, shapes, text content",
    ),
    (
        "apache-poi-shapes.pptx",
        "https://svn.apache.org/repos/asf/poi/trunk/test-data/slideshow/"
        "shapes.pptx",
        "Apache POI: Shapes test (6 slides with tables and images)",
        "PPTX",
        "6 slides with shapes, tables, image references, URLs",
    ),
    (
        "apache-poi-test.pptx",
        "https://svn.apache.org/repos/asf/poi/trunk/test-data/slideshow/"
        "pptx2svg.pptx",
        "Apache POI: Complex presentation (images and SVG content)",
        "PPTX",
        "1 slide with complex visual content (149KB)",
    ),
    (
        "apache-poi-table_test.pptx",
        "https://svn.apache.org/repos/asf/poi/trunk/test-data/slideshow/"
        "table_test.pptx",
        "Apache POI: Table test (PPTX table rendering)",
        "PPTX",
        "1 slide with a formatted table",
    ),
    (
        "tika-test.pptx",
        "https://raw.githubusercontent.com/apache/tika/refs/heads/main/"
        "tika-parsers/tika-parsers-standard/tika-parsers-standard-modules/"
        "tika-parser-microsoft-module/src/test/resources/test-documents/"
        "testPPT.pptx",
        "Apache Tika: Basic PPTX test (3 slides)",
        "PPTX",
        "3 slides with text content",
    ),
    (
        "tika-testPPT_various.pptx",
        "https://raw.githubusercontent.com/apache/tika/refs/heads/main/"
        "tika-parsers/tika-parsers-standard/tika-parsers-standard-modules/"
        "tika-parser-microsoft-module/src/test/resources/test-documents/"
        "testPPT_various.pptx",
        "Apache Tika: Various elements (speaker notes, tables)",
        "PPTX",
        "1 slide with speaker notes, tables, and various elements",
    ),
    (
        "tika-testPPT_embedded.pptx",
        "https://raw.githubusercontent.com/apache/tika/refs/heads/main/"
        "tika-parsers/tika-parsers-standard/tika-parsers-standard-modules/"
        "tika-parser-microsoft-module/src/test/resources/test-documents/"
        "testPPT_EmbeddedPDF.pptx",
        "Apache Tika: Embedded PDF in PPTX",
        "PPTX",
        "1 slide with embedded PDF as image",
    ),
    (
        "tika-testPPT_comment.pptx",
        "https://raw.githubusercontent.com/apache/tika/refs/heads/main/"
        "tika-parsers/tika-parsers-standard/tika-parsers-standard-modules/"
        "tika-parser-microsoft-module/src/test/resources/test-documents/"
        "testPPT_comment.pptx",
        "Apache Tika: PPTX with comments",
        "PPTX",
        "1 slide with comments/annotations",
    ),
    # --- DOCX ---
    (
        "section508-word-guide.docx",
        "https://assets.section508.gov/assets/files/"
        "MS%20Word%202016%20Basic%20Authoring%20and%20Testing%20Guide-AED%20COP.docx",
        "Section 508: MS Word Authoring & Testing Guide",
        "DOCX",
        "Government accessibility guide with complex tables, 24 images, "
        "hyperlinks, headings hierarchy, numbered/bulleted lists (1.8MB)",
    ),
    (
        "tika-testWORD.docx",
        "https://raw.githubusercontent.com/apache/tika/refs/heads/main/"
        "tika-parsers/tika-parsers-standard/tika-parsers-standard-modules/"
        "tika-parser-microsoft-module/src/test/resources/test-documents/"
        "testWORD.docx",
        "Apache Tika: Basic DOCX test (headings, tables, hyperlinks)",
        "DOCX",
        "Headings, tables, hyperlinks, text formatting",
    ),
    (
        "tika-testWORD_various.docx",
        "https://raw.githubusercontent.com/apache/tika/refs/heads/main/"
        "tika-parsers/tika-parsers-standard/tika-parsers-standard-modules/"
        "tika-parser-microsoft-module/src/test/resources/test-documents/"
        "testWORD_various.docx",
        "Apache Tika: Various DOCX elements",
        "DOCX",
        "Various Word elements including tables and hyperlinks",
    ),
    (
        "tika-testWORD_embedded.docx",
        "https://raw.githubusercontent.com/apache/tika/refs/heads/main/"
        "tika-parsers/tika-parsers-standard/tika-parsers-standard-modules/"
        "tika-parser-microsoft-module/src/test/resources/test-documents/"
        "testWORD_embeded.docx",
        "Apache Tika: DOCX with embedded images",
        "DOCX",
        "6 embedded images in various formats",
    ),
]


def download_all() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    for filename, url, description, fmt, notes in DOCUMENTS:
        path = SAMPLES_DIR / filename
        if path.exists():
            print(f"  ✅ Already exists: {filename} ({path.stat().st_size:,} bytes)")
            continue

        print(f"  Downloading: {description}")
        print(f"    URL: {url}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Spike004/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                path.write_bytes(resp.read())
            print(f"    ✅ Saved: {filename} ({path.stat().st_size:,} bytes)")
        except Exception as e:
            print(f"    ❌ Failed: {e}")
            print(f"    Download manually and place in: {SAMPLES_DIR / filename}")


def main() -> None:
    print("Downloading real-world documents for Spike 004...")
    print(f"Target directory: {SAMPLES_DIR}\n")
    download_all()
    print("\nDone. Run test_real_world.py to analyze conversion quality.")


if __name__ == "__main__":
    main()
