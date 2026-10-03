from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from py_idp_invoice_extractor import cli
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


def test_parse_ocr_invoice_with_spanish_dates_and_noisy_symbols():
    text = """CLIENTE: Factura n.? 12345
(55) 1234 5678
Calle 123, Ciudad, Estado, Pais. C.P. 12345
Articulo Cantidad =‘ Preelo Total
unitane
Top de camisola Eqgshell 1 $500 $500
Camisa con cuello cubano Zz £300 £600
Vestido floral de algodan 1 $400 $400
Subtotal $1,500
IVA (16%) $240
Total $1740
{Muchas gracias!
INFORMACION DE PAGO
Banco Norte
Mambre de la cuenta: Irma Lopez Rios C irq Hernandez Lo:
N.° de cuenta: 1234 567289 SONI FCrnanuies Loz
Pagar antes de: 5 de julio de 2025 Calle 123, Ciudad, Estado, Pais. C.P. 12345
Sandra Hernandez Loza
Calle 123, Ciudad, Estado, Pais. C.P. 12345"""
    extractor = InvoiceExtractor()

    parsed = extractor._parse_invoice_text(text)
    issue_date_text = "Factura n.º ABC 123\nFecha de emisión: 16 de junio de 2025"
    issue_date_parsed = extractor._parse_invoice_text(issue_date_text)

    assert parsed["vendor_name"] == "Sandra Hernandez Loza"
    assert parsed["invoice_number"] == "12345"
    assert parsed["issue_date"] is None
    assert parsed["due_date"] == "5 de julio de 2025"
    assert parsed["subtotal"] == 1500.0
    assert parsed["tax"] == 240.0
    assert parsed["total"] == 1740.0
    assert parsed["currency"] is None
    assert issue_date_parsed["issue_date"] == "16 de junio de 2025"
    assert issue_date_parsed["invoice_number"] == "ABC 123"


@pytest.mark.parametrize("output_format", ["json", "csv"])
def test_batch_processes_all_pdfs_and_records_failures(
    tmp_path, monkeypatch, capsys, output_format
):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _create_invoice_pdf(input_dir / "good.pdf")
    (input_dir / "broken.pdf").write_text("not a real PDF", encoding="utf-8")
    output_path = tmp_path / f"results.{output_format}"

    original_extract_text = InvoiceExtractor._extract_text

    def extract_text_with_failure(self, pdf_path):
        if pdf_path.name == "broken.pdf":
            raise RuntimeError("OCR failure")
        return original_extract_text(self, pdf_path)

    monkeypatch.setattr(InvoiceExtractor, "_extract_text", extract_text_with_failure)

    cli.main(
        [
            "batch",
            str(input_dir),
            "--output",
            str(output_path),
            "--format",
            output_format,
        ]
    )

    console = capsys.readouterr().out
    assert "Procesando factura 1 de 2: broken.pdf" in console
    assert "Procesando factura 2 de 2: good.pdf" in console
    assert "1 procesadas exitosamente" in console
    assert "1 fallidas" in console

    if output_format == "json":
        results = json.loads(output_path.read_text(encoding="utf-8"))
    else:
        with output_path.open(encoding="utf-8-sig", newline="") as output_file:
            results = list(csv.DictReader(output_file))

    assert len(results) == 2
    assert results[0]["file"] == "broken.pdf"
    assert results[0]["status"] == "error"
    assert "OCR failure" in results[0]["error"]
    assert results[1]["file"] == "good.pdf"
    assert results[1]["status"] == "success"
    assert results[1]["vendor_name"] == "Contoso S.L."
