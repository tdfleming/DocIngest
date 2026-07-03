# README assets

Visual assets referenced by the top-level [README](../../README.md).

| File | Used for | Status |
|------|----------|--------|
| `docingest-pipeline.svg` | Architecture / pipeline diagram | ✅ committed |
| `dashboard.png` | Dashboard screenshot | ⬜ TODO — capture from the running app |
| `search.png` | Search results screenshot | ⬜ TODO |
| `demo.gif` | End-to-end upload → search demo | ⬜ TODO |

## Capturing real UI screenshots / demo GIF

These must be captured from the **actual running app** (don't fabricate mockups):

```bash
# 1. Bring up the full stack
cp .env.example .env
docker compose up --build -d

# 2. Create a tenant API key and ingest a couple of documents
docker compose exec ingestion-api python scripts/create_api_key.py demo "Demo Tenant"

# 3. Open the UI and capture
open http://localhost:3000
#   - dashboard.png : dashboard with a few completed documents
#   - search.png    : a search query with ranked results
#   - demo.gif      : upload a file → watch status → run a search
```

Recommended: 1280×800 viewport, light theme, trim to the app chrome. Keep GIFs
under ~5 MB so they load quickly on GitHub.
