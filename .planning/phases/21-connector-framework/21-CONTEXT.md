# Phase 21 — Connector Framework

**Milestone:** v1.2 (Product Completeness) — opening phase
**Status:** 📋 Specced, not yet planned
**Author:** Product/market evaluation follow-up (2026-06-30)
**Depends on:** Core ingest pipeline (v1.0) stable. Independent of the v1.1 Graph Frontend phases (16–20).
**Related:** Outline → DocIngest → "Market & Product Evaluation" (Priority 3: connectors are the real moat)

---

## Why this phase

DocIngest today ingests via three source types: `upload`, `url`, and `watch` (folder). The market evaluation identified **connectors as the #1 Tier-1 gap** — ingestion products live or die on the breadth of sources they pull from. Buyers expect S3, Google Drive, web crawl, SharePoint, Confluence, and Slack. Without a first-class connector framework, every customer must build the hardest part (auth, pagination, incremental sync, deletion propagation) themselves, and DocIngest reads as a demo rather than a product.

This phase delivers a **pluggable connector framework** plus the first three connectors (**S3, Web Crawl, Google Drive**), designed so additional sources are additive (a new file + a registry entry) rather than structural changes.

## Goal

A tenant-scoped, incrementally-syncing connector subsystem that feeds the **existing** convert → chunk → embed → (graph) pipeline. Connectors are *source adapters only* — they discover and fetch content, then hand it to the same ingestion path already in place. They do not reimplement ingestion, chunking, or embedding.

## Core design principles

1. **Reuse the pipeline, don't fork it.** A connector's job ends at "here is a document's raw bytes + metadata + a stable external id." From there it enters the identical ingest flow (dedup via `source_hash`, `documents` record, ARQ convert job). New `source_type = "connector"`.
2. **Incremental by default.** Every sync compares the source against persisted per-item state (`external_id` + `version_token`), enqueuing only new/changed items and tombstoning deletions. Full re-crawls are an explicit override.
3. **Tenant isolation everywhere.** Connector configs, credentials, sync state, and resulting documents are all scoped by `tenant_id`, consistent with the rest of DocIngest. Each tenant configures its own connector instances.
4. **Feature-gated.** A `CONNECTORS_ENABLED` flag gates the entire subsystem end-to-end (routes 403, worker no-ops, indexes only created when true) — mirroring the established `GRAPH_RAG_ENABLED` pattern.
5. **Follow existing conventions.** Sync SDK calls (boto3, google-api-client — both synchronous) run via `loop.run_in_executor`. Heavy SDK clients use the lazy `_client` + `threading.Lock` singleton pattern. `structlog` with bound `trace_id` / `connector_id` / `tenant_id`. Config via `pydantic-settings` only.

## Architecture

### New package: `src/docingest/connectors/`

```
connectors/
├── base.py         # Connector Protocol, ConnectorItem, SyncResult, SyncContext
├── registry.py     # ConnectorType → Connector implementation registry
├── sync.py         # Source-agnostic sync engine (list → diff → enqueue/tombstone → checkpoint)
├── s3.py           # S3 / S3-compatible (MinIO, R2, Wasabi) connector
├── webcrawl.py     # Seed-URL web crawler (depth + domain scoping, robots.txt aware)
└── gdrive.py       # Google Drive connector (OAuth2, changes API for incremental)
```

### The Connector contract (`base.py`)

```python
class ConnectorItem(BaseModel):
    external_id: str          # stable id within the source (S3 key, Drive fileId, URL)
    version_token: str        # etag / mtime / content hash — changes iff content changes
    source_ref: str           # human-readable ref stored on the document record
    content_type: str | None  # hint; final type resolved at conversion
    metadata: dict = {}

class SyncResult(BaseModel):
    enqueued: int
    unchanged: int
    tombstoned: int
    cursor: str | None        # opaque, persisted for the next incremental run
    errors: list[str] = []

class Connector(Protocol):
    type: ConnectorType

    async def validate(self, config: ConnectorConfig) -> None:
        """Test credentials/reachability. Raise ConnectorConfigError on failure."""

    def list_items(
        self, config: ConnectorConfig, cursor: str | None
    ) -> AsyncIterator[ConnectorItem]:
        """Yield items since `cursor`. Full listing when cursor is None."""

    async def fetch(self, config: ConnectorConfig, item: ConnectorItem) -> bytes:
        """Return raw bytes for a single item (executor-wrapped if the SDK is sync)."""
```

### Sync engine (`sync.py`) — source-agnostic

```
1. Load connector config + last cursor + item-state map from connector_store
2. for item in connector.list_items(config, cursor):
       prior = state_map.get(item.external_id)
       if prior is None or prior.version_token != item.version_token:
           bytes = await connector.fetch(config, item)
           enqueue ingest (source_type="connector", source_ref, dedup via source_hash)
           record/refresh item state (external_id, version_token, doc_id)
       else:
           unchanged += 1
3. Deletion pass (full syncs only): external_ids in state_map but absent from
   this listing → tombstone → DELETE document + Qdrant points + graph data
   (reuse the Phase 13 lifecycle cleanup helpers)
4. Persist new cursor + updated state map; write SyncResult to sync history
```

### New model: `models/connector.py`

- `ConnectorType(StrEnum)` — `s3`, `web_crawl`, `google_drive` (extensible).
- `ConnectorConfig` — `id`, `tenant_id`, `type`, `name`, `enabled`, `schedule_cron` (nullable), `config` (type-specific dict), `secret_ref`, `created_at`, `updated_at`.
- `SyncStatus(StrEnum)` — `idle`, `syncing`, `succeeded`, `failed`.
- `ConnectorRun` — per-sync record: `connector_id`, `started_at`, `finished_at`, `status`, `SyncResult` fields, `error_type` / `error_stage`.

### New DB helpers: `db/connector_store.py`

- Collections: `connectors` (config), `connector_items` (per-item state map: `(tenant_id, connector_id, external_id)` unique), `connector_runs` (history).
- `ensure_connector_indexes()` — called from `app.py` lifespan only when `CONNECTORS_ENABLED` (mirrors `ensure_graph_indexes`).
- CRUD + cursor/state persistence helpers. Do not bypass these from routes/worker.

### New worker: `workers/sync_worker.py`

- Queue `arq:queue:sync`, max 4 concurrent, 15-min timeout, 2 retries (30s delay).
- Job `run_connector_sync(connector_id)` → resolve config → dispatch to registry → run sync engine → write `ConnectorRun`.
- Scheduling: ARQ cron entries generated per enabled connector from `schedule_cron`; also invoked on-demand from the API. No-op immediately if `CONNECTORS_ENABLED` is false.

### New routes: `api/routes/connectors.py` (mounted under `/v1/connectors`, API-key auth, `Tenant` dep)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/connectors` | Create a connector config (validates credentials) |
| `GET` | `/v1/connectors` | List tenant connectors |
| `GET` | `/v1/connectors/{id}` | Get config + latest sync status |
| `PATCH` | `/v1/connectors/{id}` | Update config / enable / disable |
| `DELETE` | `/v1/connectors/{id}` | Remove connector (optionally tombstone its documents) |
| `POST` | `/v1/connectors/{id}/sync` | Trigger a sync (incremental default, `?full=true` override) |
| `GET` | `/v1/connectors/{id}/runs` | Paginated sync history |

All 403 when `CONNECTORS_ENABLED` is false.

### Frontend: `pages/ConnectorsPage.tsx` + `components/connectors/`

- List of configured connectors with status badges (idle/syncing/succeeded/failed) and last-run summary.
- Add/edit connector modal (type-specific config forms: S3 bucket/prefix/endpoint, crawl seed URLs/depth/domain, Drive OAuth connect).
- "Sync now" + per-connector run history drawer. Reuse the existing TanStack Query + Axios client patterns.

## The first three connectors

| Connector | `list_items` cursor | `version_token` | Auth | Notes |
|-----------|---------------------|-----------------|------|-------|
| **S3** | `ContinuationToken` + stored `StartAfter` key | object `ETag` | access key/secret + endpoint (works with MinIO/R2/Wasabi) | boto3 (sync) → executor; lazy client singleton |
| **Web Crawl** | frontier serialization / last-crawl timestamp | content SHA-256 | none (public) | depth + same-domain scoping, `robots.txt` honored, `httpx.AsyncClient` reuse |
| **Google Drive** | Drive `changes` API `pageToken` | file `md5Checksum` / `modifiedTime` | OAuth2 (offline refresh token) | `changes.list` gives true incremental + deletions natively |

## Scope

### In scope
- Connector framework (base contract, registry, source-agnostic sync engine, incremental state, deletion propagation).
- Three connectors: S3, Web Crawl, Google Drive.
- Config store, sync worker + scheduling, REST API, frontend management page.
- `CONNECTORS_ENABLED` feature gate end-to-end.
- Tests: sync-engine diff/tombstone logic (mocked connector), one connector integration test, config-store CRUD.

### Out of scope (defer to later v1.2 phases)
- SharePoint, Confluence, Slack connectors (framework must make these additive; implementation deferred).
- OCR of fetched scanned files (separate Tier-1 phase).
- Secret-manager integration (Vault/KMS) — v1.2 uses env/`.env` refs or MongoDB with an at-rest note; document the limitation.
- Real-time push/webhook sync — polling + cron only for this phase.
- Per-document ACL mirroring from the source — tenant-level isolation only, consistent with v1.

## Requirements (CONN-xx)

- **CONN-01** — `Connector` Protocol + `ConnectorItem` / `SyncResult` models exist in `connectors/base.py`.
  - *DoD:* Protocol defines `validate`, `list_items`, `fetch`; `ConnectorItem` has `external_id`, `version_token`, `source_ref`.
- **CONN-02** — `ConnectorType` enum + `ConnectorConfig` / `ConnectorRun` models in `models/connector.py`.
  - *DoD:* `ConnectorType` has ≥3 values; config carries `tenant_id`, `type`, `enabled`, `schedule_cron`, `config`, `secret_ref`.
- **CONN-03** — `connector_store.py` CRUD + `ensure_connector_indexes` gated by `CONNECTORS_ENABLED`.
  - *DoD:* unique index on `(tenant_id, connector_id, external_id)`; indexes created in lifespan only when flag true.
- **CONN-04** — Source-agnostic sync engine performs list → diff → enqueue/tombstone → checkpoint.
  - *DoD:* unchanged items are skipped; changed items re-enqueue; cursor persisted; unit test with a mocked connector asserts the three counters.
- **CONN-05** — Incremental sync via `version_token`; unchanged items are not re-ingested.
- **CONN-06** — Deletion propagation: items absent on a full sync are tombstoned and their document + vectors + graph data removed (reuses Phase 13 cleanup).
- **CONN-07** — S3 connector: lists/fetches from an S3-compatible endpoint with continuation + ETag versioning; sync SDK calls executor-wrapped.
- **CONN-08** — Web Crawl connector: depth + same-domain scoping, `robots.txt` honored, content-hash versioning.
- **CONN-09** — Google Drive connector: OAuth2 with refresh token; incremental via `changes` API `pageToken`, including native deletions.
- **CONN-10** — Sync worker on queue `arq:queue:sync`; no-ops when `CONNECTORS_ENABLED` is false.
- **CONN-11** — Scheduled syncs via per-connector `schedule_cron` (ARQ cron) + on-demand `POST /v1/connectors/{id}/sync`.
- **CONN-12** — `/v1/connectors` CRUD + sync/runs routes, API-key + `Tenant` scoped, 403 when flag off.
- **CONN-13** — Frontend Connectors page: list, add/edit, sync-now, run history.
- **CONN-14** — `CONNECTORS_ENABLED` gates the subsystem end-to-end (lifespan indexes, worker, routes).
- **CONN-15** — New source type `connector` on the document model; ingestion dedups via existing `source_hash`.

## Proposed plan breakdown

| Plan | Scope | Key requirements |
|------|-------|------------------|
| 21-01 | Models + config store + feature gate + indexes | CONN-02, CONN-03, CONN-14, CONN-15 |
| 21-02 | Base contract + registry + source-agnostic sync engine (mocked connector tests) | CONN-01, CONN-04, CONN-05, CONN-06 |
| 21-03 | S3 connector | CONN-07 |
| 21-04 | Web Crawl connector | CONN-08 |
| 21-05 | Google Drive connector (OAuth) | CONN-09 |
| 21-06 | Sync worker + ARQ cron scheduling | CONN-10, CONN-11 |
| 21-07 | Connectors REST API | CONN-12 |
| 21-08 | Frontend Connectors page | CONN-13 |

## Key risks & decisions

| Risk / decision | Mitigation / recommendation |
|-----------------|-----------------------------|
| **Secret storage** in OSS single-node has no KMS | v1.2: store as `secret_ref` → env var or MongoDB field with an at-rest-encryption note in docs; design `secret_ref` indirection now so Vault/KMS is a later swap, not a schema change. |
| **OAuth flow (Drive)** needs a redirect/callback + token refresh | Add a minimal OAuth callback route; store refresh token via `secret_ref`. Consider service-account JSON as the simpler first path for headless deployments. |
| **Crawl politeness / runaway crawls** | Enforce depth cap, domain allowlist, `robots.txt`, and a max-pages ceiling in config; log dropped/over-limit URLs (no silent truncation). |
| **Large sources** overwhelming the queue | Batch enqueue with backpressure; sync worker paces enqueues; document per-tenant concurrency expectations. |
| **Deletion on incremental (non-full) syncs** | Only tombstone on full syncs, or when the source API reports deletions natively (Drive `changes`). Incremental S3/crawl runs do not infer deletions from absence. |
| **Connector = new moat, so keep it OSS** | Per the market decision, connectors stay in the Apache-2.0 core; *managed* connector hosting/credential vaulting is the paid-cloud upsell. |

## Verification criteria (phase-level)

- `docker compose up` with `CONNECTORS_ENABLED=true` starts a `sync-worker` service; with the flag false the `/v1/connectors` routes return 403 and no connector indexes are created.
- Configuring an S3 connector against a local MinIO bucket and triggering a sync ingests every object exactly once; a second sync reports all items `unchanged` and enqueues nothing.
- Changing one object's content and re-syncing re-ingests only that object.
- A full sync after deleting a source object tombstones the corresponding document and removes its Qdrant points (and graph data when `GRAPH_RAG_ENABLED`).
- `pytest tests/test_connector_sync.py` (mocked connector) passes for the enqueue/unchanged/tombstone paths.
- `ruff check src/` clean.
