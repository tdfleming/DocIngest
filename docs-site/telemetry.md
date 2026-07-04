# Telemetry

!!! success "Off by default"
    DocIngest collects **no telemetry unless you explicitly opt in**. Nothing leaves
    your machine otherwise — owning your data is the whole point.

## What you can opt into

Setting `TELEMETRY_ENABLED=true` starts an anonymous heartbeat every
`TELEMETRY_INTERVAL_HOURS` (default 24h) so maintainers can gauge how many instances are
running and on what versions. Sending is best-effort and **fail-silent** — it can never
affect the application.

## Exactly what a heartbeat contains

```json
{
  "event": "heartbeat",
  "instance_id": "a3f9c1…",        // random, generated once; not tied to anything
  "version": "0.1.0",
  "os": "Linux",
  "python": "3.12",
  "documents": "10-99",             // coarse bucket, never an exact count
  "graph_rag_enabled": false
}
```

It **never** sends document content, tenant data, API keys, file names, IP addresses, or
any personal data.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEMETRY_ENABLED` | `false` | Master switch. Off unless you set it. |
| `TELEMETRY_ENDPOINT` | `https://telemetry.docingest.dev/v1/heartbeat` | Where heartbeats are sent (configurable — point it at your own collector) |
| `TELEMETRY_INTERVAL_HOURS` | `24` | Heartbeat interval |

## Turning it off

It's already off. If you enabled it and want to stop, set `TELEMETRY_ENABLED=false` (or
remove the variable) and restart. The instance id lives in a `telemetry` collection in
MongoDB; drop it if you want to reset.
