from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any

from .extractor import InvoiceExtractor


_BATCH_FIELDS = [
    "file",
    "status",
    "error",
    "vendor_name",
    "invoice_number",
    "issue_date",
    "due_date",
    "subtotal",
    "tax",
    "total",
    "currency",
    "raw_fields",
]


def main(argv: list[str] | None = None) -> None:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments and arguments[0].lower() == "batch":
        _run_batch(arguments[1:])
        return

    parser = argparse.ArgumentParser(description="Extrae datos de facturas desde PDFs.")
    parser.add_argument("pdf_path", help="Ruta del PDF a procesar")
    parser.add_argument(
        "--output",
        "-o",
        help="Ruta donde guardar el JSON de salida (opcional)",
    )
    args = parser.parse_args(arguments)

    extractor = InvoiceExtractor()
    result = extractor.extract_to_dict(args.pdf_path)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Resultado guardado en: {output_path}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


def _run_batch(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m py_idp_invoice_extractor.cli batch",
        description="Procesa por lotes los PDFs de una carpeta.",
    )
    parser.add_argument("input_dir", help="Carpeta que contiene los PDFs")
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Archivo consolidado de salida",
    )
    parser.add_argument(
        "--format",
        choices=("csv", "json"),
        default="json",
        help="Formato del archivo de salida (por defecto: json)",
    )
    args = parser.parse_args(argv)

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        parser.error(f"la carpeta de entrada no existe: {input_dir}")

    pdf_files = sorted(
        (path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"),
        key=lambda path: path.name.casefold(),
    )
    extractor = InvoiceExtractor()
    results: list[dict[str, Any]] = []

    for index, pdf_path in enumerate(pdf_files, start=1):
        print(f"Procesando factura {index} de {len(pdf_files)}: {pdf_path.name}")
        try:
            invoice = extractor.extract_to_dict(pdf_path)
            results.append(
                {
                    "file": pdf_path.name,
                    "status": "success",
                    "error": "",
                    **invoice,
                }
            )
        except Exception as error:
            results.append(
                {
                    "file": pdf_path.name,
                    "status": "error",
                    "error": f"{type(error).__name__}: {error}",
                }
            )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "json":
        output_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        with output_path.open("w", encoding="utf-8-sig", newline="") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=_BATCH_FIELDS)
            writer.writeheader()
            for result in results:
                row = {field: result.get(field, "") for field in _BATCH_FIELDS}
                if isinstance(row["raw_fields"], dict):
                    row["raw_fields"] = json.dumps(row["raw_fields"], ensure_ascii=False)
                writer.writerow(row)

    succeeded = sum(result["status"] == "success" for result in results)
    failed = len(results) - succeeded
    print(f"Resumen: {succeeded} procesadas exitosamente; {failed} fallidas.")
    print(f"Resultado guardado en: {output_path}")


if __name__ == "__main__":
    main()
