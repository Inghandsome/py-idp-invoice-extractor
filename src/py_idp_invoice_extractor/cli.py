from __future__ import annotations

import argparse
import json
from pathlib import Path

from .extractor import InvoiceExtractor


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrae datos de facturas desde PDFs.")
    parser.add_argument("pdf_path", help="Ruta del PDF a procesar")
    parser.add_argument(
        "--output",
        "-o",
        help="Ruta donde guardar el JSON de salida (opcional)",
    )
    args = parser.parse_args()

    extractor = InvoiceExtractor()
    result = extractor.extract_to_dict(args.pdf_path)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Resultado guardado en: {output_path}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
