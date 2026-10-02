# py-idp-invoice-extractor

Extractor de datos de facturas en PDF con IA, basado en py-idp para procesado inteligente de documentos.

## Objetivo

Construir una herramienta que lea facturas en PDF y extraiga campos clave como:

- nombre del proveedor
- número de factura
- fecha de emisión
- fecha de vencimiento
- subtotal
- impuestos
- total
- moneda

## Estructura inicial del proyecto

- `src/py_idp_invoice_extractor/` — código fuente principal
- `pyproject.toml` — configuración del proyecto
- `requirements.txt` — dependencias mínimas
- `data/` — para añadir PDFs de pruebas
- `output/` — salida JSON o archivos procesados

## Requisitos

- Python 3.10+
- pip

## Instalación

```bash
python -m venv .venv
. .venv/bin/activate  # Linux/macOS
# o .\.venv\Scripts\activate  # Windows PowerShell
pip install -r requirements.txt
```

## Uso

Ejecuta el extractor sobre un PDF:

```bash
python -m py_idp_invoice_extractor.cli "ruta/al/archivo.pdf"
```

También puedes guardar el resultado en JSON:

```bash
python -m py_idp_invoice_extractor.cli "ruta/al/archivo.pdf" --output output/result.json
```

## Estado actual

Este repositorio ya tiene la estructura base de un proyecto Python para empezar a desarrollar la lógica de extracción con py-idp. La implementación actual es un esqueleto funcional para que podamos ir completando la integración real con el motor de IA y la extracción de campos.

## Siguientes pasos sugeridos

1. definir el esquema real de salida JSON
2. conectar la lógica con py-idp y el modelo de extracción
3. añadir pruebas con PDFs reales de facturas
4. validar la extracción sobre varios formatos y proveedores
5. preparar una CLI más robusta y un flujo de procesamiento por lote

## Notas

La configuración actual usa variables de entorno opcionales:

- `IDP_INPUT_DIR`
- `IDP_OUTPUT_DIR`
- `IDP_MODEL_NAME`
- `IDP_TEMPERATURE`
