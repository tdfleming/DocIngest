# Deployment

## Docker Compose (single server)

The simplest deployment. Everything — API, workers, frontend, and datastores — runs on one machine.

```bash
git clone https://github.com/tdfleming/DocIngest && cd DocIngest
cp .env.example .env
# Edit .env — at minimum change JWT_SECRET_KEY and MinIO credentials
docker compose up --build -d
docker compose ps            # verify health
```

Scale workers independently:

```bash
docker compose up --scale converter-worker=4 --scale chunker-worker=4 -d
```

## Kubernetes (Helm)

A Kubernetes-agnostic chart lives in [`deploy/helm/docingest`](https://github.com/tdfleming/DocIngest/tree/master/deploy/helm/docingest). It deploys the API, workers, and frontend, with bundled MongoDB/Qdrant/Redis/MinIO enabled by default for parity with Compose.

```bash
helm install docingest ./deploy/helm/docingest \
  --namespace docingest --create-namespace \
  --set secrets.jwtSecretKey="$(openssl rand -hex 32)"
```

### Production: managed datastores

Per the project's infra guidance, run the stateful layer as **managed services** and disable the bundled ones:

```yaml
# prod-values.yaml
mongodb: { enabled: false }
qdrant:  { enabled: false }
redis:   { enabled: false }
minio:   { enabled: false }

externalDatastores:
  mongodbUri: "mongodb+srv://user:pass@cluster.example.net"
  qdrantHost: "qdrant.example.net"
  redisUrl:   "redis://redis.example.net:6379"
  minioEndpoint: "s3.amazonaws.com"

config:
  minioSecure: "true"

secrets:
  existingSecret: docingest-secrets   # holds JWT_SECRET_KEY, MINIO_ACCESS_KEY, MINIO_SECRET_KEY

ingress:
  enabled: true
  className: nginx
  host: docingest.example.com
```

```bash
helm install docingest ./deploy/helm/docingest -n docingest --create-namespace -f prod-values.yaml
```

See the [chart README](https://github.com/tdfleming/DocIngest/blob/master/deploy/helm/docingest/README.md) for the full values reference, ingress, autoscaling, and image build/push instructions.

## Container images

Published to GHCR on each release tag:

```
ghcr.io/tdfleming/docingest-{api,frontend,converter,chunker,graph-worker}
```

Tags: `<version>`, `<major>.<minor>`, `latest`, `sha-<short>` (`linux/amd64`).

## Health & probes

`GET /v1/health` checks connectivity to all four datastores concurrently and returns per-service status (`200` healthy / `503` degraded). Use it as a **readiness** probe; use a plain TCP/process check for **liveness** so a transient datastore outage doesn't restart the API (the Helm chart already does this).

## Backups

| Store | Strategy |
|-------|----------|
| MongoDB | `mongodump` on a schedule |
| Qdrant | Snapshot API or volume backup |
| MinIO / S3 | `mc mirror` to another target |
| Redis | Ephemeral job state — no backup needed |
