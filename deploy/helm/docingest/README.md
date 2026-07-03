# DocIngest Helm Chart

Kubernetes-agnostic Helm chart for [DocIngest](https://github.com/tdfleming/DocIngest) —
the multi-tenant document ingestion engine (API, workers, frontend) plus optional
bundled datastores.

## What it deploys

| Workload | Kind | Default |
|---|---|---|
| `ingestion-api` | Deployment + Service | 2 replicas |
| `frontend` | Deployment + Service | 1 replica |
| `converter-worker` | Deployment | 2 replicas |
| `chunker-worker` | Deployment | 2 replicas |
| `graph-worker` | Deployment | disabled (opt-in) |
| MongoDB / Qdrant / Redis / MinIO | StatefulSet + headless Service | bundled (opt-out) |

## Quick start (self-host, everything bundled)

```bash
# Build & push images to your registry first (see below), then:
helm install docingest ./deploy/helm/docingest \
  --namespace docingest --create-namespace \
  --set secrets.jwtSecretKey="$(openssl rand -hex 32)"
```

This brings up the full stack — mirroring `docker-compose up` — including in-cluster
MongoDB, Qdrant, Redis, and MinIO.

## Production (managed datastores)

Per the project's infra guidance, **run the stateful layer as managed services** and
disable the bundled ones:

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
  # Prefer an externally-managed Secret over inline values:
  existingSecret: docingest-secrets   # must hold JWT_SECRET_KEY, MINIO_ACCESS_KEY, MINIO_SECRET_KEY

ingress:
  enabled: true
  className: nginx
  host: docingest.example.com
```

```bash
helm install docingest ./deploy/helm/docingest -n docingest --create-namespace -f prod-values.yaml
```

## Images

The chart references `{{ global.imageRegistry }}/<component>:<tag>` (tag defaults to the
chart `appVersion`). Until an automated image-publish workflow exists, build and push from
the repo root:

```bash
REG=ghcr.io/tdfleming; TAG=0.1.0
for c in api frontend converter chunker graph-worker; do
  docker build -f docker/$c.Dockerfile -t $REG/docingest-$c:$TAG .
  docker push $REG/docingest-$c:$TAG
done
```

## Enabling Graph RAG

```bash
helm upgrade docingest ./deploy/helm/docingest --reuse-values \
  --set config.graphRagEnabled=true --set graphWorker.enabled=true
```

## Key values

See [`values.yaml`](values.yaml) for the full list. Common overrides:
`api.replicaCount`, `api.autoscaling.enabled`, `*.resources`, `*.persistence.size`,
`ingress.*`, `global.imagePullSecrets`.

## Frontend → API routing

The frontend image's nginx proxies `/v1` to `http://ingestion-api:8000`, so the API
Service is named `ingestion-api` by default (`api.service.name`). When using Ingress,
`/v1` is routed to the API and `/` to the frontend directly.
