from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from py_idp_invoice_extractor.extractor import InvoiceExtractor


def _create_invoice_pdf(path: Path) -> None:
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Contoso S.L.", styles["Title"]))
    story.append(Paragraph("Invoice #INV-2048", styles["Heading2"]))
    story.append(Paragraph("Issue Date: 2026-09-15", styles["BodyText"]))
    story.append(Paragraph("Due Date: 2026-09-30", styles["BodyText"]))
    story.append(Spacer(1, 12))

    table_data = [
        ["Description", "Amount"],
        ["Consulting services", "€1,000.00"],
        ["VAT (21%)", "€210.00"],
        ["Total", "€1,210.00"],
    ]
    table = Table(table_data, colWidths=[300, 120])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(table)
    doc.build(story)


def test_extract_invoice_from_pdf(tmp_path):
    pdf_path = tmp_path / "invoice.pdf"
    _create_invoice_pdf(pdf_path)

    result = InvoiceExtractor().extract(pdf_path)

    assert result.vendor_name == "Contoso S.L."
    assert result.invoice_number == "INV-2048"
    assert result.issue_date == "2026-09-15"
    assert result.due_date == "2026-09-30"
    assert result.currency == "EUR"
    assert result.subtotal == 1000.0
    assert result.tax == 210.0
    assert result.total == 1210.0
