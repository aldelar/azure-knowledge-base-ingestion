#!/usr/bin/env python3
"""Create sample PDF, PPTX, and DOCX files for spike 004.

Generates test documents with embedded images, tables, headings,
and (for PPTX) speaker notes — covering the features that matter
most for conversion quality assessment.

Usage:
    cd src/functions && uv run python ../spikes/004-pdf-pptx-conversion/create_samples.py
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"


def _create_test_image(filename: str, width: int = 300, height: int = 200, color: str = "blue") -> Path:
    """Create a simple test PNG image."""
    img = Image.new("RGB", (width, height), color)
    path = SAMPLES_DIR / filename
    img.save(path)
    return path


def create_sample_pdf() -> Path:
    """Create a sample PDF with headings, tables, images, and links."""
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    # Create test images first
    img1_path = _create_test_image("diagram-architecture.png", 400, 250, "steelblue")
    img2_path = _create_test_image("chart-performance.png", 350, 200, "darkorange")

    pdf_path = SAMPLES_DIR / "sample-article.pdf"
    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
    styles = getSampleStyleSheet()
    story: list = []

    # Title
    story.append(Paragraph("Azure Knowledge Base Architecture Guide", styles["Title"]))
    story.append(Spacer(1, 0.25 * inch))

    # Introduction paragraph
    story.append(Paragraph("Introduction", styles["Heading1"]))
    story.append(Paragraph(
        "This document describes the architecture of the Azure Knowledge Base system. "
        "The system uses Azure AI Search for retrieval-augmented generation (RAG) and "
        "Azure OpenAI Service for natural language understanding.",
        styles["Normal"],
    ))
    story.append(Spacer(1, 0.15 * inch))

    # Embedded image 1
    story.append(Paragraph("System Architecture", styles["Heading2"]))
    story.append(Paragraph(
        "The following diagram shows the high-level architecture of the system:",
        styles["Normal"],
    ))
    story.append(Spacer(1, 0.1 * inch))
    story.append(RLImage(str(img1_path), width=4 * inch, height=2.5 * inch))
    story.append(Spacer(1, 0.15 * inch))

    # Table
    story.append(Paragraph("Component Overview", styles["Heading2"]))
    table_data = [
        ["Component", "Service", "Purpose", "SKU"],
        ["Search Index", "Azure AI Search", "Vector + keyword search", "Standard S1"],
        ["LLM", "Azure OpenAI", "GPT-4.1 for generation", "Standard"],
        ["Storage", "Azure Blob Storage", "KB article files", "Standard LRS"],
        ["Identity", "Azure Entra ID", "Authentication & RBAC", "P1"],
        ["Monitoring", "Application Insights", "Telemetry & logging", "Pay-as-you-go"],
    ]
    table = Table(table_data, colWidths=[1.2 * inch, 1.5 * inch, 2 * inch, 1.3 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#D9E2F3")]),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.15 * inch))

    # More content with sub-headings
    story.append(Paragraph("Deployment Options", styles["Heading2"]))
    story.append(Paragraph("Container Apps Hosting", styles["Heading3"]))
    story.append(Paragraph(
        "The agent is deployed as an Azure Container App with managed identity enabled. "
        "Environment variables are configured via Bicep templates, and secrets are stored "
        "in Azure Key Vault.",
        styles["Normal"],
    ))

    story.append(Paragraph("Scaling Configuration", styles["Heading3"]))
    story.append(Paragraph(
        "Auto-scaling is configured based on HTTP request concurrency. The minimum replica "
        "count is set to 1 for development environments and 3 for production.",
        styles["Normal"],
    ))

    # Second image
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph("Performance Metrics", styles["Heading2"]))
    story.append(RLImage(str(img2_path), width=3.5 * inch, height=2 * inch))
    story.append(Spacer(1, 0.15 * inch))

    # Bullet points
    story.append(Paragraph("Key Features", styles["Heading2"]))
    bullets = [
        "Retrieval-augmented generation with hybrid search (vector + keyword)",
        "Image-grounded responses using GPT-4.1 vision capabilities",
        "Per-request context isolation using Python ContextVar",
        "Managed identity for all service-to-service authentication",
        "Infrastructure as Code using Bicep templates",
    ]
    for bullet in bullets:
        story.append(Paragraph(f"• {bullet}", styles["Normal"]))

    # Second table
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph("API Endpoints", styles["Heading2"]))
    api_table_data = [
        ["Endpoint", "Method", "Description"],
        ["/api/chat", "POST", "Send a chat message to the agent"],
        ["/api/health", "GET", "Health check endpoint"],
        ["/api/convert-markitdown", "POST", "Convert HTML to Markdown"],
        ["/api/index", "POST", "Index articles into AI Search"],
    ]
    api_table = Table(api_table_data, colWidths=[2 * inch, 1 * inch, 3 * inch])
    api_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(api_table)

    # Build PDF
    doc.build(story)
    print(f"  Created PDF: {pdf_path} ({pdf_path.stat().st_size:,} bytes)")
    return pdf_path


def create_sample_pptx() -> Path:
    """Create a sample PPTX with slides, speaker notes, images, and tables."""
    from pptx import Presentation
    from pptx.util import Inches, Pt

    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    # Create test images
    img1_path = _create_test_image("slide-diagram.png", 500, 300, "teal")
    img2_path = _create_test_image("slide-chart.png", 400, 300, "coral")

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # Slide 1: Title slide
    slide1 = prs.slides.add_slide(prs.slide_layouts[0])
    slide1.shapes.title.text = "Azure KB Agent Architecture"
    slide1.placeholders[1].text = "PDF/PPTX Conversion Quality Spike\nMarch 2026"
    notes1 = slide1.notes_slide
    notes1.notes_text_frame.text = (
        "Welcome to the architecture overview for the Azure KB Agent. "
        "This presentation covers the key components, deployment strategy, "
        "and performance characteristics of the system. "
        "IMPORTANT: Mention that we use managed identity everywhere — no secrets in code."
    )

    # Slide 2: Content with bullet points
    slide2 = prs.slides.add_slide(prs.slide_layouts[1])
    slide2.shapes.title.text = "System Components"
    body2 = slide2.placeholders[1]
    tf2 = body2.text_frame
    tf2.text = "Core Services"
    for item in [
        "Azure AI Search — hybrid vector + keyword retrieval",
        "Azure OpenAI — GPT-4.1 for generation and vision",
        "Azure Blob Storage — KB article staging and serving",
        "Azure Container Apps — serverless hosting",
        "Azure Cosmos DB — conversation memory",
    ]:
        p = tf2.add_paragraph()
        p.text = item
        p.level = 1
    notes2 = slide2.notes_slide
    notes2.notes_text_frame.text = (
        "Emphasize that all services communicate via managed identity. "
        "No connection strings or API keys are stored in application code. "
        "The Container Apps use DefaultAzureCredential for authentication. "
        "Cosmos DB uses native RBAC with Built-in Data Contributor role."
    )

    # Slide 3: Image slide
    slide3 = prs.slides.add_slide(prs.slide_layouts[5])  # Blank layout
    slide3.shapes.title.text = "Architecture Diagram"
    slide3.shapes.add_picture(str(img1_path), Inches(2), Inches(2), Inches(9), Inches(4.5))
    notes3 = slide3.notes_slide
    notes3.notes_text_frame.text = (
        "This diagram shows the data flow from HTML ingestion through "
        "conversion (MarkItDown), indexing (AI Search), to the agent query path. "
        "Key point: the conversion pipeline supports three backends — "
        "Content Understanding, Mistral Document AI, and MarkItDown."
    )

    # Slide 4: Table slide
    slide4 = prs.slides.add_slide(prs.slide_layouts[5])
    slide4.shapes.title.text = "Conversion Backend Comparison"
    rows, cols = 5, 4
    table_shape = slide4.shapes.add_table(rows, cols, Inches(1), Inches(2), Inches(11), Inches(4))
    tbl = table_shape.table
    headers = ["Backend", "API Calls", "Image Handling", "Cost"]
    data = [
        ["Content Understanding", "CU API", "CU Analyzer", "CU + GPT-4.1"],
        ["Mistral Document AI", "Mistral OCR", "GPT-4.1 Vision", "Mistral + GPT-4.1"],
        ["MarkItDown", "None (local)", "GPT-4.1 Vision", "GPT-4.1 only"],
        ["MarkItDown + PDF", "TBD", "TBD", "TBD"],
    ]
    for ci, h in enumerate(headers):
        tbl.cell(0, ci).text = h
    for ri, row_data in enumerate(data, 1):
        for ci, val in enumerate(row_data):
            tbl.cell(ri, ci).text = val
    notes4 = slide4.notes_slide
    notes4.notes_text_frame.text = (
        "The MarkItDown backend is the most cost-effective option. "
        "The PDF row is for this spike — we are evaluating whether "
        "MarkItDown can handle PDF input directly with acceptable quality."
    )

    # Slide 5: Second image + conclusion
    slide5 = prs.slides.add_slide(prs.slide_layouts[5])
    slide5.shapes.title.text = "Performance Results"
    slide5.shapes.add_picture(str(img2_path), Inches(3), Inches(2), Inches(7), Inches(4))
    notes5 = slide5.notes_slide
    notes5.notes_text_frame.text = (
        "Performance chart shows that MarkItDown is 10x faster than cloud-based "
        "alternatives for text extraction. Image description time is the same "
        "across all backends since they all use GPT-4.1 vision."
    )

    pptx_path = SAMPLES_DIR / "sample-presentation.pptx"
    prs.save(str(pptx_path))
    print(f"  Created PPTX: {pptx_path} ({pptx_path.stat().st_size:,} bytes)")
    return pptx_path


def create_sample_docx() -> Path:
    """Create a sample DOCX with headings, tables, and an image."""
    from docx import Document
    from docx.shared import Inches

    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    img_path = _create_test_image("docx-diagram.png", 400, 250, "forestgreen")

    doc = Document()
    doc.add_heading("Azure KB Agent Setup Guide", level=0)
    doc.add_paragraph(
        "This guide covers the setup and configuration of the Azure Knowledge Base Agent "
        "for local development and Azure deployment."
    )

    doc.add_heading("Prerequisites", level=1)
    doc.add_paragraph("Python 3.11+", style="List Bullet")
    doc.add_paragraph("Azure CLI with active subscription", style="List Bullet")
    doc.add_paragraph("Azure Developer CLI (azd)", style="List Bullet")
    doc.add_paragraph("Docker Desktop", style="List Bullet")

    doc.add_heading("Architecture Overview", level=1)
    doc.add_paragraph("The following diagram shows the deployment architecture:")
    doc.add_picture(str(img_path), width=Inches(4.5))

    doc.add_heading("Environment Variables", level=1)
    table = doc.add_table(rows=5, cols=3, style="Table Grid")
    headers = ["Variable", "Required", "Description"]
    for ci, h in enumerate(headers):
        table.cell(0, ci).text = h
    env_vars = [
        ("AI_SERVICES_ENDPOINT", "Yes", "Azure AI Services endpoint URL"),
        ("SEARCH_ENDPOINT", "Yes", "Azure AI Search endpoint URL"),
        ("SERVING_BLOB_ENDPOINT", "Yes", "Blob storage endpoint for serving"),
        ("COSMOS_ENDPOINT", "No", "Cosmos DB endpoint for memory"),
    ]
    for ri, (var, req, desc) in enumerate(env_vars, 1):
        table.cell(ri, 0).text = var
        table.cell(ri, 1).text = req
        table.cell(ri, 2).text = desc

    doc.add_heading("Deployment Steps", level=1)
    doc.add_paragraph("Run azd up to provision and deploy all resources.", style="List Number")
    doc.add_paragraph("Configure environment with azd env get-values.", style="List Number")
    doc.add_paragraph("Run make test to verify the deployment.", style="List Number")

    docx_path = SAMPLES_DIR / "sample-document.docx"
    doc.save(str(docx_path))
    print(f"  Created DOCX: {docx_path} ({docx_path.stat().st_size:,} bytes)")
    return docx_path


def main() -> None:
    print("Creating sample documents for Spike 004...")
    create_sample_pdf()
    create_sample_pptx()
    create_sample_docx()
    print("Done — all samples in", SAMPLES_DIR)


if __name__ == "__main__":
    main()
