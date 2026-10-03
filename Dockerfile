FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt pyproject.toml README.md ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
RUN pip install --no-cache-dir -e .

EXPOSE 10000

CMD ["sh", "-c", "uvicorn py_idp_invoice_extractor.web:app --host 0.0.0.0 --port ${PORT:-10000}"]