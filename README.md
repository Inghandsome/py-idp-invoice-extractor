# Extractor de facturas PDF

Herramienta Python para extraer campos habituales de facturas en PDF: proveedor,
número de factura, fechas, subtotal, impuestos, total y moneda. Usa `pdfplumber`
para PDFs con texto nativo y `pytesseract` con `pdf2image` para aplicar OCR a
PDFs escaneados.

El resultado se puede imprimir como JSON, guardar para un PDF individual o
consolidar en un único archivo JSON o CSV para una carpeta completa.

## Requisitos previos

- Python 3.11 o posterior.
- Tesseract OCR instalado en Windows. Descarga:
  [UB Mannheim Tesseract builds](https://github.com/UB-Mannheim/tesseract/wiki)
- Poppler para Windows. Descarga:
  [Poppler for Windows releases](https://github.com/oschwartz10612/poppler-windows/releases/)
- Git y pip.

Las rutas de los ejecutables de Tesseract y Poppler están configuradas en
`.env` mediante `TESSERACT_CMD` (ruta al ejecutable
`tesseract.exe`) y `POPPLER_PATH` (carpeta `bin` de Poppler). Copia
`.env.example` a `.env` y cambia esos valores si instalaste las herramientas
en otras ubicaciones. Si las variables no están definidas, se usan las rutas
por defecto de Windows incluidas en `extractor.py`; ya no es necesario editar
el código para configurar instalaciones distintas.

## Instalación

Abre PowerShell y clona el repositorio:

```powershell
git clone URL_DEL_REPOSITORIO
cd py-idp-invoice-extractor
```

Reemplaza `URL_DEL_REPOSITORIO` por la URL Git del proyecto. Crea y activa un
entorno virtual, instala las dependencias y registra el paquete localmente:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
```

Si PowerShell bloquea la activación del entorno, puedes invocar sus ejecutables
directamente con `.\.venv\Scripts\python.exe` y
`.\.venv\Scripts\pip.exe`.

## Uso

### Procesar un PDF

Imprime el resultado JSON en la consola:

```powershell
python -m py_idp_invoice_extractor.cli data/input/factura.pdf
```

Guarda el resultado en un archivo:

```powershell
python -m py_idp_invoice_extractor.cli data/input/factura.pdf --output output/factura.json
```

### Procesar una carpeta

El comando procesa los archivos `.pdf` directamente dentro de la carpeta
indicada, muestra el progreso y continúa si alguno falla. Cada registro incluye
su estado; los errores se guardan en el campo `error`.

Consolidado JSON:

```powershell
python -m py_idp_invoice_extractor.cli batch data/input --output output/lote.json --format json
```

Consolidado CSV:

```powershell
python -m py_idp_invoice_extractor.cli batch data/input --output output/lote.csv --format csv
```

Si se omite `--format`, el formato predeterminado es JSON. La CLI muestra una
línea por PDF, seguida del resumen de procesados exitosamente y fallidos.

### Interfaz web local

Inicia el servidor de desarrollo desde la raíz del repositorio:

```powershell
uvicorn py_idp_invoice_extractor.web:app --reload
```

Abre `http://127.0.0.1:8000` en el navegador y selecciona un PDF de hasta 10 MB.
El resultado de la extracción se muestra como JSON en la página.

### Construir y probar con Docker

Desde la raíz del repositorio, construye la imagen:

```powershell
docker build -t py-idp-invoice-extractor .
```

Inicia el contenedor localmente. Por defecto, escucha en el puerto `10000`:

```powershell
docker run --rm -p 10000:10000 py-idp-invoice-extractor
```

Abre `http://localhost:10000` para probar el formulario. La imagen instala
Tesseract con el paquete de idioma español y Poppler; en Linux, el extractor usa
`tesseract` y encuentra las herramientas de Poppler desde el `PATH` del sistema.
Para usar otro puerto local, pasa el mismo valor en `PORT` y en el puerto del
contenedor, por ejemplo `docker run --rm -e PORT=8080 -p 8080:8080
py-idp-invoice-extractor`.

### Ejemplo de salida JSON

La ejecución individual devuelve un objeto con los campos de factura y el texto
extraído en `raw_fields`:

```json
{
  "vendor_name": "Contoso S.L.",
  "invoice_number": "INV-2048",
  "issue_date": "2026-09-15",
  "due_date": "2026-09-30",
  "subtotal": 1000.0,
  "tax": 210.0,
  "total": 1210.0,
  "currency": "EUR",
  "raw_fields": {
    "source_file": "data/input/factura.pdf",
    "raw_text": "Contoso S.L.\nInvoice #INV-2048\n..."
  }
}
```

El modo por lotes produce una lista de objetos similares, con los campos
adicionales `file`, `status` y `error` para identificar el archivo y registrar
fallos.

## Estructura del proyecto

- `src/py_idp_invoice_extractor/cli.py`: comandos para procesar PDFs individuales
  o carpetas, mostrar progreso y escribir JSON o CSV.
- `src/py_idp_invoice_extractor/web.py`: interfaz web FastAPI para subir un PDF y
  recibir los datos extraídos como JSON.
- `src/py_idp_invoice_extractor/extractor.py`: extracción de texto con
  `pdfplumber`, OCR de PDFs escaneados y análisis heurístico de campos.
- `src/py_idp_invoice_extractor/models.py`: modelo `InvoiceData`, que define los
  campos devueltos para cada factura.
- `src/py_idp_invoice_extractor/config.py`: carga variables de entorno
  opcionales para las rutas de entrada/salida y ajustes del modelo.
- `src/py_idp_invoice_extractor/__init__.py`: expone `InvoiceExtractor` como
  interfaz del paquete.
- `tests/test_extractor.py`: pruebas de extracción, parseo OCR y procesamiento
  por lotes en JSON y CSV.
- `tests/test_web.py`: pruebas de la página web, validación de archivos, límite
  de tamaño y respuesta del endpoint de extracción.
- `data/input/`: carpeta sugerida para PDFs de entrada.
- `output/`: carpeta sugerida para resultados.

## Pruebas

Con el entorno virtual activado, ejecuta:

```powershell
python -m pytest
```

Para ejecutar solo las pruebas del extractor:

```powershell
python -m pytest tests/test_extractor.py -q
```

## Limitaciones conocidas

- La extracción de campos usa reglas y patrones; las facturas con diseños muy
  distintos pueden requerir ajustes.
- El OCR puede confundir símbolos de moneda. Si detecta símbolos contradictorios,
  la moneda puede quedar como `null`; revisa `raw_fields.raw_text`.
- Las fechas de emisión no se pueden extraer si no aparecen en el documento o si
  el OCR no las reconoce. Las fechas en palabras se reconocen en patrones como
  `16 de junio de 2025` cuando están junto a una etiqueta de fecha admitida.
- La calidad del OCR depende de la resolución y legibilidad del escaneo, y de
  que Tesseract y Poppler estén instalados y sus rutas estén bien configuradas.
- El demo público en Render usa un plan con memoria limitada (512 MB) y reduce
  el OCR a 150 DPI. Aun así, PDFs grandes o con muchas páginas pueden consumir
  demasiada memoria y fallar; localmente se conserva la resolución de 300 DPI.
- El procesamiento por lotes no entra en subcarpetas; procesa solo los PDFs
  ubicados directamente en la carpeta indicada.
- `pdfplumber` y OCR pueden no recuperar texto de PDFs dañados o protegidos. En
  esos casos, inspecciona el estado del registro y el contenido extraído.