FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir . \
    && python -m spacy download en_core_web_lg

CMD ["arq", "docingest.workers.graph_builder.WorkerSettings"]
