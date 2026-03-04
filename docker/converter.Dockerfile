FROM python:3.12-slim

WORKDIR /app

# Docling needs system deps for PDF parsing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

CMD ["arq", "docingest.workers.converter.WorkerSettings"]
