# API Reference

All endpoints are versioned under `/v1/`. DocIngest uses two auth mechanisms:

- **API key** (`X-API-Key` header) — document, search, and graph endpoints
- **JWT** (`Authorization: Bearer …`) — user and API-key management (`/v1/auth/*`, `/v1/admin/*`)

**API key scopes.** Keys can be restricted to least-privilege scopes: `read`
(search + reads), `ingest` (create/delete/reprocess documents), and `admin`
(everything, including graph rebuild). A key with no scopes has full access, so
existing keys keep working. Set scopes when creating a key via `POST /v1/admin/api-keys`.

A running instance also serves interactive docs at `/docs` (Swagger UI) and `/redoc`.

**Usage.** `GET /v1/usage` returns the caller tenant's usage totals per event type
(`ingest`, `search`, …) for the current calendar month — the basis for quotas and billing.

**Plans & subscriptions.** `GET /v1/plans` lists the plan catalog (tier, price, monthly
limits). `GET /v1/subscription` returns the active org's subscription, defaulting to the
free plan when none is set; `PUT /v1/subscription` (OWNER/ADMIN) changes the org's plan.

**Quota enforcement.** When `QUOTA_ENFORCEMENT_ENABLED=true`, ingest and search requests
that would exceed the active plan's monthly limit are rejected with `402 Payment Required`.
It is OFF by default, so self-hosted deployments stay unmetered.

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
