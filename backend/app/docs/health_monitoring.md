# Health Check Monitoring and Alerts

## Endpoint

`GET /api/v1/health`

The endpoint verifies connectivity to all critical runtime dependencies:

- **Database** — executes `SELECT 1` against the primary Postgres connection.
- **Redis** — issues a `PING` against the configured Redis instance.

### Responses

`200 OK` — every dependency is reachable:

```json
{
  "status": "healthy",
  "project": "Stellarts",
  "database": "healthy",
  "redis": "healthy",
  "debug": false
}
```

`503 Service Unavailable` — any dependency is unreachable. The response body
still includes per-component status so alerts can identify which subsystem
failed.

## External Uptime Monitor (UptimeRobot)

Configure a monitor with the following settings:

| Field              | Value                                              |
| ------------------ | -------------------------------------------------- |
| Monitor Type       | HTTP(s) — Keyword                                  |
| URL                | `https://api.<your-domain>/api/v1/health`          |
| Keyword Type       | Exists                                             |
| Keyword            | `"status":"healthy"`                               |
| Monitoring Interval| 1 minute                                           |
| HTTP Method        | GET                                                |

The keyword match ensures the monitor flags downtime when any dependency
reports `unhealthy`, even if the HTTP status is somehow 200.

Create an equivalent monitor for each RPC node the backend depends on,
pointing at their respective health/ping endpoints.

## Alert Channels

Under **My Settings → Alert Contacts** in UptimeRobot, configure:

1. **Email** — the on-call distribution list (e.g. `oncall@stellarts.io`).
2. **Slack** — incoming webhook for the `#alerts-infra` channel. Generate it
   from Slack's _Incoming Webhooks_ app and paste it into the
   _Add Alert Contact → Slack_ dialog.

Attach both contacts to every health-check monitor. Recommended thresholds:

- Notify **when down** after 2 consecutive failures.
- Notify **when back up** immediately.
- Escalate to PagerDuty (optional) after 5 minutes of continuous downtime.

## Local Verification

```bash
curl -i http://localhost:8000/api/v1/health
```

A healthy local stack returns `200` with all components reporting `healthy`.
Stop Redis or Postgres to confirm the endpoint correctly returns `503`.
