from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile

import pdfplumber
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from .extractor import InvoiceExtractor

MAX_FILE_SIZE = 10 * 1024 * 1024

app = FastAPI(title="Extractor de facturas PDF")


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Extractor de facturas</title>
  <style>
    :root { color-scheme: light; font-family: "Segoe UI", sans-serif; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center;
           background: #f2f5f3; color: #1d2924; }
    main { width: min(560px, calc(100% - 40px)); padding: 32px;
           background: #fff; border: 1px solid #d9e2dc; border-radius: 12px;
           box-shadow: 0 12px 36px #183c2514; }
    h1 { margin: 0 0 8px; font-size: 1.6rem; }
    p { color: #53645a; line-height: 1.5; }
    form { display: grid; gap: 16px; margin-top: 24px; }
    input[type=file] { width: 100%; padding: 12px; border: 1px solid #c9d5cd;
                       border-radius: 7px; box-sizing: border-box; }
    button { justify-self: start; padding: 11px 18px; border: 0; border-radius: 7px;
             background: #176b4b; color: white; font: inherit; font-weight: 600;
             cursor: pointer; }
    button:disabled { opacity: .6; cursor: wait; }
    #result { margin-top: 20px; padding: 14px; overflow-wrap: anywhere;
              background: #f5f8f6; border-radius: 7px; white-space: pre-wrap; }
    #result:empty { display: none; }
  </style>
</head>
<body>
  <main>
    <h1>Extractor de facturas</h1>
    <p>Selecciona un PDF de hasta 10 MB para extraer sus datos.</p>
    <form id="upload-form">
      <input name="file" type="file" accept="application/pdf,.pdf" required>
      <button type="submit">Extraer datos</button>
    </form>
    <pre id="result" aria-live="polite"></pre>
  </main>
  <script>
    const form = document.querySelector("#upload-form");
    const result = document.querySelector("#result");
    const button = form.querySelector("button");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      result.textContent = "Procesando PDF...";
      button.disabled = true;
      try {
        const response = await fetch("/extract", {
          method: "POST",
          body: new FormData(form)
        });
        const payload = await response.json();
        result.textContent = JSON.stringify(payload, null, 2);
      } catch (error) {
        result.textContent = `No se pudo completar la solicitud: ${error}`;
      } finally {
        button.disabled = false;
      }
    });
  </script>
</body>
</html>"""


@app.post("/extract")
async def extract_invoice(file: UploadFile = File(...)) -> dict:
    content = await file.read(MAX_FILE_SIZE + 1)
    await file.close()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="El archivo supera el límite permitido de 10 MB.",
        )
    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=415,
            detail="El archivo subido no parece ser un PDF válido.",
        )

    try:
        with pdfplumber.open(BytesIO(content)) as document:
            if not document.pages:
                raise ValueError("El PDF no contiene páginas.")
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail="El PDF está dañado, protegido o no se puede leer.",
        ) from error

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)

        result = InvoiceExtractor().extract_to_dict(temporary_path)
    except Exception as error:
        raise HTTPException(
            status_code=422,
            detail=f"Falló la extracción del PDF: {type(error).__name__}: {error}",
        ) from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    raw_fields = result.get("raw_fields") or {}
    if not raw_fields.get("raw_text", "").strip():
        raise HTTPException(
            status_code=422,
            detail="No se pudo extraer texto. Comprueba la calidad del PDF y la configuración de Tesseract/Poppler.",
        )
    return result
