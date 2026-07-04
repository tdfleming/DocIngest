# API Reference

All endpoints are versioned under `/v1/`. DocIngest uses two auth mechanisms:

- **API key** (`X-API-Key` header) — document, search, and graph endpoints
- **JWT** (`Authorization: Bearer …`) — user and API-key management (`/v1/auth/*`, `/v1/admin/*`)

A running instance also serves interactive docs at `/docs` (Swagger UI) and `/redoc`.

The full specification below is generated from the FastAPI app at build time.

<div id="redoc-container"></div>
<script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
<script>
  Redoc.init('../openapi.json', { hideDownloadButton: false, expandResponses: '200,201' },
             document.getElementById('redoc-container'));
</script>

<noscript>
The interactive reference requires JavaScript. The raw spec is available at
<a href="../openapi.json">openapi.json</a>.
</noscript>
