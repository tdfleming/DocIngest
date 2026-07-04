# DocIngest

**The open-source ingestion backend for RAG.** Drop-in, multi-tenant: document → clean Markdown → semantic chunks → vectors → knowledge graph. Self-host it free, or run it managed. Own your data, own your pipeline.

![DocIngest pipeline](https://raw.githubusercontent.com/tdfleming/DocIngest/master/docs/assets/docingest-pipeline.svg){ width="100%" }

Point DocIngest at a PDF, DOCX, HTML, TXT, or Markdown file and it converts to clean Markdown (IBM Docling), splits into semantic chunks, generates embeddings locally (FastEmbed — no API keys), stores them in Qdrant, and — optionally — extracts an entity/relationship knowledge graph. Every layer is tenant-isolated.

## Run it in one command

```bash
git clone https://github.com/tdfleming/DocIngest && cd DocIngest
cp .env.example .env
docker compose up --build
```

Then open the UI at `http://localhost:3000` or the API at `http://localhost:8000`.

## Where to go next

<div class="grid cards" markdown>

- **[Getting Started](getting-started.md)** — install, first API key, first upload & search
- **[Configuration](configuration.md)** — environment variables
- **[Graph RAG](graph-rag.md)** — entities, relationships, communities
- **[Deployment](deployment.md)** — Docker Compose & Kubernetes/Helm
- **[API Reference](api-reference.md)** — full OpenAPI spec
- **[Benchmarks](benchmarks.md)** — comparison & performance harness

</div>

## Why DocIngest

Ingestion is the ugliest, most re-invented part of every RAG stack — and the layer you re-index again and again as chunking and embedding strategies change. DocIngest packages it as a real, self-hostable service that is, uniquely, **permissive OSS + genuinely multi-tenant + graph-capable + with a managed path**. Because embeddings and reranking run locally, there's no per-token cost and re-indexing is essentially free.

Licensed under **Apache-2.0**.
