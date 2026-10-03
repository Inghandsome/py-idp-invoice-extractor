from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from py_idp_invoice_extractor.extractor import InvoiceExtractor
from py_idp_invoice_extractor.web import MAX_FILE_SIZE, app

client = TestClient(app)


def _pdf_bytes() -> bytes:
    buffer = BytesIO()
    document = canvas.Canvas(buffer)
    document.drawString(72, 720, "Contoso S.L.")
    document.drawString(72, 690, "Invoice #INV-2048")
    document.save()
    return buffer.getvalue()


def test_homepage_contains_pdf_upload_form():
    response = client.get("/")

    assert response.status_code == 200
    assert 'action="/extract"' not in response.text
    assert 'name="file" type="file"' in response.text
    assert "10 MB" in response.text


def test_extract_endpoint_returns_invoice_json():
    response = client.post(
        "/extract",
        files={"file": ("invoice.pdf", _pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["vendor_name"] == "Contoso S.L."
    assert response.json()["invoice_number"] == "INV-2048"


def test_extract_endpoint_rejects_non_pdf_upload():
    response = client.post(
        "/extract",
        files={"file": ("invoice.txt", b"not a PDF", "text/plain")},
    )

    assert response.status_code == 415
    assert "PDF válido" in response.json()["detail"]


def test_extract_endpoint_rejects_files_over_size_limit():
    response = client.post(
        "/extract",
        files={
            "file": (
                "large.pdf",
                b"%PDF-" + b"0" * MAX_FILE_SIZE,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    assert "10 MB" in response.json()["detail"]


def test_extract_endpoint_reports_extraction_errors(monkeypatch):
    def fail_extraction(self, pdf_path):
        raise RuntimeError("OCR no disponible")

    monkeypatch.setattr(InvoiceExtractor, "extract_to_dict", fail_extraction)
    response = client.post(
        "/extract",
        files={"file": ("invoice.pdf", _pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 422
    assert "OCR no disponible" in response.json()["detail"]
