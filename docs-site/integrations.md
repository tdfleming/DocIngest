# MCP & CLI

DocIngest ships two developer surfaces on top of the REST API, both driven by the same
client and configured with `DOCINGEST_API_URL` / `DOCINGEST_API_KEY`.

## MCP server

Expose DocIngest to AI agents (Claude Code, Cursor, Claude Desktop) as MCP tools — so an
agent can ingest documents and search your corpus directly.

Install the extra and confirm the entry point:

```bash
pip install "docingest[mcp]"
docingest-mcp   # runs the server over stdio
```

### Tools

| Tool | Description |
|------|-------------|
| `ingest_document(source, wait)` | Ingest an http(s) URL or local file path |
| `search(query, limit)` | Semantic search (vector + reranking) |
| `get_document_status(document_id)` | Processing status & metadata |
| `list_documents(status, limit)` | List ingested documents |
| `graph_search(query, limit)` | Search knowledge-graph summaries (needs `GRAPH_RAG_ENABLED`) |

### Connect it

=== "Claude Code"

    ```bash
    claude mcp add docingest \
      --env DOCINGEST_API_URL=http://localhost:8000 \
      --env DOCINGEST_API_KEY=<your-key> \
      -- docingest-mcp
    ```

=== "Claude Desktop / Cursor (JSON)"

    ```json
    {
      "mcpServers": {
        "docingest": {
          "command": "docingest-mcp",
          "env": {
            "DOCINGEST_API_URL": "http://localhost:8000",
            "DOCINGEST_API_KEY": "<your-key>"
          }
        }
      }
    }
    ```

## CLI

A thin client for scripting and quick checks.

```bash
export DOCINGEST_API_URL=http://localhost:8000
export DOCINGEST_API_KEY=<your-key>

docingest ingest ./report.pdf --wait      # file, directory, or URL
docingest search "quarterly revenue" --limit 5
docingest list --status complete
docingest status <doc-id>
docingest health
```

Add `--json` to any command to also print the raw API response for scripting. Configuration
can also be passed per-command with `--api-url` / `--api-key`.
