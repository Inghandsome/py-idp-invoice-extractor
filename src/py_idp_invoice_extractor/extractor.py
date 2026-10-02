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
            images = convert_from_path(str(pdf_path), dpi=300)
            chunks = []
            for image in images:
                chunks.append(pytesseract.image_to_string(image, config="--psm 6"))
            return "\n".join(chunks).strip()
        except Exception:
            return ""

    def _parse_invoice_text(self, text: str) -> dict[str, Any]:
        normalized = re.sub(r"\s+", " ", text or "").strip()
        lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
        vendor_name = self._find_vendor_name(lines)
        invoice_number = self._find_first_match(
            normalized,
            r"(?:invoice(?:\s*no|\s*#)?|factura(?:\s*no|\s*#)?|invoice\s+number|n[úu]mero\s+de\s+factura|num\.?\s*factura)[^A-Z0-9-]*([A-Z0-9-]+)",
            flags=re.IGNORECASE,
        )
        issue_date = self._find_date(normalized, r"(?:issue date|issued on|fecha de emisi[oó]n|fecha de emisión|emitido el|fecha emisi[oó]n)", "issue")
        due_date = self._find_date(normalized, r"(?:due date|payment due|vencimiento|fecha de vencimiento|fecha vencimiento)", "due")
        currency = self._find_currency(normalized)
        amounts = self._find_amounts(lines)
        subtotal = self._find_amount_by_label(lines, r"subtotal|base imponible|net total|net amount")
        tax = self._find_amount_by_label(lines, r"tax|vat|iva|impuesto")
        total = self._find_amount_by_label(lines, r"total|total due|importe total")

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
        for line in lines:
            if re.search(r"(?:invoice|factura|total|subtotal|tax|vat|iva)", line, re.IGNORECASE):
                continue
            if len(line) <= 120 and not re.fullmatch(r"[\d\s\-#.:/()]+", line):
                return line
        return lines[0] if lines else None

    def _find_first_match(self, text: str, pattern: str, flags: int = 0) -> str | None:
        match = re.search(pattern, text, flags)
        if not match:
            return None
        groups = match.groups()
        if not groups:
            return None
        return str(groups[0]).strip()

    def _find_date(self, text: str, pattern: str, date_type: str) -> str | None:
        match = re.search(
            r"""(?:%s)[^0-9]{0,20}(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"""
            % pattern,
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
        return None

    def _find_currency(self, text: str) -> str | None:
        if re.search(r"(?:€|EUR|\?)", text, re.IGNORECASE):
            return "EUR"
        if re.search(r"(?:\$|USD)", text, re.IGNORECASE):
            return "USD"
        if re.search(r"(?:£|GBP)", text, re.IGNORECASE):
            return "GBP"
        return None

    def _parse_money_value(self, value: str) -> float | None:
        cleaned = value.strip().replace(" ", "")
        if not cleaned:
            return None
        cleaned = cleaned.replace("€", "").replace("£", "").replace("$", "").replace("?", "")
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(".") > cleaned.rfind(","):
                cleaned = cleaned.replace(",", "")
            else:
                cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            if cleaned.count(",") > 1:
                cleaned = cleaned.replace(",", "")
            else:
                cleaned = cleaned.replace(",", ".")
        elif "." in cleaned and cleaned.count(".") > 1:
            cleaned = cleaned.replace(".", "")

        try:
            return float(cleaned)
        except ValueError:
            return None

    def _find_amounts(self, lines: list[str]) -> list[float]:
        values: list[float] = []
        for line in lines:
            if not re.search(r"(?:€|£|\$|EUR|USD|GBP|\?|total|subtotal|tax|vat|iva|amount|balance)", line, re.IGNORECASE):
                continue
            for value in re.findall(r"(?<![A-Za-z])([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{2})|[0-9]+(?:[.,][0-9]{2}))", line):
                numeric = self._parse_money_value(value)
                if numeric is not None and numeric > 0:
                    values.append(numeric)
        return values

    def _find_amount_by_label(self, lines: list[str], label_pattern: str) -> float | None:
        label_re = re.compile(label_pattern, re.IGNORECASE)
        for line in lines:
            if not label_re.search(line):
                continue
            match = re.search(r"(?<![A-Za-z])([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{2})|[0-9]+(?:[.,][0-9]{2}))", line)
            if not match:
                continue
            value = match.group(1)
            numeric = self._parse_money_value(value)
            if numeric is not None:
                return numeric
        return None
