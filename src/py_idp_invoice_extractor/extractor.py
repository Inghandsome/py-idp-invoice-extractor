from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import settings
from .models import InvoiceData

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None

try:
    import pytesseract
    from pdf2image import convert_from_path
except ImportError:  # pragma: no cover
    pytesseract = None
    convert_from_path = None

if pytesseract is not None:
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

POPPLER_PATH = r"C:\poppler-26.09.0\Library\bin"


class InvoiceExtractor:
    """Extrae datos de facturas a partir de PDFs normales o escaneados."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.model_name

    def extract(self, pdf_path: str | Path) -> InvoiceData:
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"El archivo no existe: {path}")

        text = self._extract_text(path)
        parsed = self._parse_invoice_text(text)

        invoice = InvoiceData(
            vendor_name=parsed.get("vendor_name"),
            invoice_number=parsed.get("invoice_number"),
            issue_date=parsed.get("issue_date"),
            due_date=parsed.get("due_date"),
            subtotal=parsed.get("subtotal"),
            tax=parsed.get("tax"),
            total=parsed.get("total"),
            currency=parsed.get("currency"),
            raw_fields={
                "source_file": str(path),
                "raw_text": text,
            },
        )
        return invoice

    def extract_to_dict(self, pdf_path: str | Path) -> dict[str, Any]:
        invoice = self.extract(pdf_path)
        return invoice.__dict__

    def _extract_text(self, pdf_path: Path) -> str:
        if pdfplumber is not None:
            text = self._extract_with_pdfplumber(pdf_path)
            if text:
                return text

        if pytesseract is not None and convert_from_path is not None:
            text = self._extract_with_ocr(pdf_path)
            if text:
                return text

        return ""

    def _extract_with_pdfplumber(self, pdf_path: Path) -> str:
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                pages = []
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    if text:
                        pages.append(text)
                return "\n".join(pages).strip()
        except Exception:
            return ""

    def _extract_with_ocr(self, pdf_path: Path) -> str:
        try:
            images = convert_from_path(str(pdf_path), dpi=300, poppler_path=POPPLER_PATH)
            chunks = []
            for image in images:
                chunks.append(pytesseract.image_to_string(image, config="--psm 6"))
                width, height = image.size
                footer = image.crop(
                    (int(width * 0.42), int(height * 0.82), int(width * 0.98), int(height * 0.98))
                )
                footer_text = pytesseract.image_to_string(footer, config="--psm 6")
                if footer_text:
                    chunks.append(footer_text)
            return "\n".join(chunks).strip()
        except Exception:
            return ""

    def _parse_invoice_text(self, text: str) -> dict[str, Any]:
        normalized = re.sub(r"\s+", " ", text or "").strip()
        lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
        vendor_name = self._find_vendor_name(lines)
        invoice_number = self._find_first_match(
            normalized,
            r"(?:invoice|factura)\s*(?:(?:n(?:[.º°o]|[.]\s*[º°])?|num(?:ero)?|number|no\.?|#)\s*)?[:#º°.,?¿¡\-]*\s*([A-Z0-9]+(?:[ ./_-][A-Z0-9]+){0,3}?)(?=\s*(?:\(|fecha|date|issue|due|pagar|$))",
            flags=re.IGNORECASE,
        )
        issue_date = self._find_date(normalized, r"(?:issue date|issued on|fecha de emisi[oó]n|emitido el|fecha emisi[oó]n)", "issue")
        due_date = self._find_date(normalized, r"(?:due date|payment due|pagar antes de|vencimiento|fecha de vencimiento|fecha vencimiento)", "due")
        currency = self._find_currency(normalized)
        amounts = self._find_amounts(lines)
        subtotal = self._find_amount_by_label(lines, r"subtotal|base imponible|net total|net amount")
        tax = self._find_amount_by_label(lines, r"tax|vat|iva|impuesto")
        total = self._find_amount_by_label(lines, r"\b(?:total(?:\s+due)?|importe total)\b")

        if subtotal is None and amounts:
            subtotal = amounts[0]
        if tax is None and len(amounts) >= 2 and (total is not None or len(amounts) >= 2):
            tax = amounts[1] if total is not None and len(amounts) > 1 else amounts[1]
        if total is None and amounts:
            total = amounts[-1]
        if total is not None and subtotal is not None and tax is None:
            tax = round(max(total - subtotal, 0.0), 2)

        return {
            "vendor_name": vendor_name,
            "invoice_number": invoice_number,
            "issue_date": issue_date,
            "due_date": due_date,
            "subtotal": subtotal,
            "tax": tax,
            "total": total,
            "currency": currency,
        }

    def _find_vendor_name(self, lines: list[str]) -> str | None:
        seller_labels = r"(?:vendedor|proveedor|seller|emisor|issued\s+by|from)\s*[:：-]\s*(.+)"
        for line in reversed(lines):
            match = re.search(seller_labels, line, re.IGNORECASE)
            if match:
                candidate = self._clean_vendor_candidate(match.group(1))
                if candidate:
                    return candidate

        payment_start = next(
            (
                index
                for index, line in enumerate(lines)
                if re.search(r"(?:informaci[oó]n|datos)\s+de\s+pago|payment\s+(?:information|details)", line, re.IGNORECASE)
            ),
            None,
        )
        if payment_start is not None:
            for line in reversed(lines[payment_start + 1 :]):
                if self._is_non_vendor_line(line):
                    continue
                name = re.search(
                    r"\b([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+(?:\s+[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+){1,3})\b",
                    line,
                )
                if name:
                    return name.group(1)

        for line in lines[:5]:
            if re.search(r"(?:invoice|factura)", line, re.IGNORECASE):
                break
            if self._is_non_vendor_line(line):
                continue
            candidate = self._clean_vendor_candidate(line)
            if candidate:
                return candidate
        return None

    def _is_non_vendor_line(self, line: str) -> bool:
        excluded = (
            r"(?:cliente|calle|avenida|av\.?|street|road|c\.?p\.?|código postal|postal|"
            r"tel[eé]fono|phone|banco|bank|cuenta|account|pagar antes|fecha|date|"
            r"muchas gracias|thank|invoice|factura|description|amount|art[ií]culo|"
            r"cantidad|subtotal|total|tax|vat|iva|nombre de la cuenta|n\.?[º°]\s*de cuenta)"
        )
        return bool(
            re.search(excluded, line, re.IGNORECASE)
            or re.search(r"\d{3,}|[$£€¥₹¢?]\s*\d", line)
        )

    def _clean_vendor_candidate(self, value: str) -> str | None:
        candidate = re.split(r"\s{2,}|\s+[|•]\s+", value.strip())[0].strip(" :,-")
        if len(candidate) < 3 or not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", candidate):
            return None
        if re.search(r"\d{3,}", candidate):
            return None
        return candidate[:120]

    def _find_first_match(self, text: str, pattern: str, flags: int = 0) -> str | None:
        match = re.search(pattern, text, flags)
        if not match:
            return None
        groups = match.groups()
        if not groups:
            return None
        return str(groups[0]).strip()

    def _find_date(self, text: str, pattern: str, date_type: str) -> str | None:
        date_value = r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+de\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+\s+de\s+\d{4})"
        match = re.search(
            r"(?:%s)[^0-9]{0,40}%s" % (pattern, date_value),
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
        return None

    def _find_currency(self, text: str) -> str | None:
        if re.search(r"EUR|€", text, re.IGNORECASE):
            return "EUR"
        if re.search(r"USD", text, re.IGNORECASE):
            return "USD"
        if re.search(r"GBP", text, re.IGNORECASE):
            return "GBP"
        has_dollar = re.search(r"\$", text) is not None
        has_pound = re.search(r"£", text) is not None
        if has_dollar and has_pound:
            return None
        if has_dollar:
            return "USD"
        if has_pound:
            return "GBP"
        return None

    def _parse_money_value(self, value: str) -> float | None:
        cleaned = value.strip().replace(" ", "")
        if not cleaned:
            return None
        cleaned = re.sub(r"[^\d.,+-]", "", cleaned)
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(".") > cleaned.rfind(","):
                cleaned = cleaned.replace(",", "")
            else:
                cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            if cleaned.count(",") > 1 or len(cleaned.rsplit(",", 1)[1]) == 3:
                cleaned = cleaned.replace(",", "")
            else:
                cleaned = cleaned.replace(",", ".")
        elif "." in cleaned:
            if cleaned.count(".") > 1 or len(cleaned.rsplit(".", 1)[1]) == 3:
                cleaned = cleaned.replace(".", "")

        try:
            return float(cleaned)
        except ValueError:
            return None

    def _find_amounts(self, lines: list[str]) -> list[float]:
        values: list[float] = []
        amount_pattern = r"(?<![A-Za-z])(?:[0-9]{1,3}(?:[.,\s][0-9]{3})+|[0-9]+)(?:[.,][0-9]{2})?(?![A-Za-z])"
        for line in lines:
            if not re.search(r"(?:total|subtotal|tax|vat|iva|amount|balance|[$£€¥₹¢?])", line, re.IGNORECASE):
                continue
            for value in re.findall(amount_pattern, line):
                numeric = self._parse_money_value(value)
                if numeric is not None and numeric > 0:
                    values.append(numeric)
        return values

    def _find_amount_by_label(self, lines: list[str], label_pattern: str) -> float | None:
        label_re = re.compile(label_pattern, re.IGNORECASE)
        amount_pattern = r"(?<![A-Za-z])(?:[0-9]{1,3}(?:[.,\s][0-9]{3})+|[0-9]+)(?:[.,][0-9]{2})?(?![A-Za-z])"
        for line in lines:
            if not label_re.search(line):
                continue
            matches = re.findall(amount_pattern, line)
            if not matches:
                continue
            numeric = self._parse_money_value(matches[-1])
            if numeric is not None:
                return numeric
        return None