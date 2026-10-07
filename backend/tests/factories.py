"""Test factories: generate real PDFs in memory (reportlab)."""

import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer


def make_test_pdf(
    title: str, sections: list[tuple[str, str]], filename: str = "test.pdf"
) -> tuple[str, bytes]:
    """Build a multi-page PDF.

    ``sections``: list of (heading, body); each section starts on a new page
    after the first, so page-number metadata is meaningful.
    Returns (filename, pdf_bytes).
    """
    styles = getSampleStyleSheet()
    story: list = [Paragraph(title, styles["Heading1"]), Spacer(1, 24)]
    for i, (heading, body) in enumerate(sections):
        if i > 0:
            story.append(PageBreak())
        story.append(Paragraph(heading, styles["Heading2"]))
        story.append(Paragraph(body, styles["Normal"]))
        story.append(Spacer(1, 12))
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4).build(story)
    return filename, buf.getvalue()


def make_encrypted_pdf() -> bytes:
    """A password-protected PDF (must be rejected at validation)."""
    from pypdf import PdfReader, PdfWriter

    _, data = make_test_pdf("Secret", [("H", "classified body")])
    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt("s3cret")
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
