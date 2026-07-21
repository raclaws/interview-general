# Webhook Contract: CF Worker → interview-general

## Context

Replaces NocoDB webhook. CF Worker sits between Google Form and Neon (canonical store), then forwards candidate events to interview-general's SQLite via webhook.

```
Google Form → Apps Script → CF Worker → Neon (write)
                                      → POST /api/webhooks/candidates (interview-general)
```

## Endpoint

```
POST /api/webhooks/candidates
Authorization: Bearer {WEBHOOK_SECRET}
Content-Type: application/json
```

Auth changed from `X-Webhook-Secret` header to standard `Authorization: Bearer` — easier to configure in CF Worker `fetch()`.

## Payload Shape

```json
{
  "event": "candidate.created" | "candidate.updated" | "candidate.deleted",
  "timestamp": "2026-07-21T10:30:00Z",
  "source": "google_form" | "manual" | "bulk",
  "data": {
    "external_id": 4946,
    "name": "Hadi Permana",
    "email": "hadi.prmn@gmail.com",
    "phone": "081234567890",
    "current_position": "Backend Developer",
    "yoe": "3",
    "languages": "Python",
    "cloud": "AWS",
    "tools": "Docker, Kubernetes",
    "working_arrangement": "Remote, Hybrid",
    "current_salary": "",
    "expected_salary": "9500000",
    "notice_period": "1 Month",
    "cv_link": "https://drive.google.com/open?id=..."
  }
}
```

## Field Mapping

| Webhook field | Candidate model field | Notes |
|---------------|----------------------|-------|
| `external_id` | `external_id` (was `nocodb_id`) | Neon row ID, unique per candidate |
| `name` | `name` | Required |
| `email` | `email` | Required, used as dedup key |
| `phone` | `phone` | Optional |
| `current_position` | `current_position` | Optional |
| `yoe` | `yoe` | Optional, string |
| `languages` | `languages` | Optional |
| `cloud` | `cloud` | Optional |
| `tools` | `tools` | Optional |
| `working_arrangement` | `working_arrangement` | Optional |
| `current_salary` | `current_salary` | Optional, string (IDR) |
| `expected_salary` | `expected_salary` | Optional, string (IDR) |
| `notice_period` | `notice_period` | Optional |
| `cv_link` | `cv_link` | Optional, Google Drive URL |

## Events

### `candidate.created`
- Upsert by email (find-or-create)
- Set `external_id` from payload
- If candidate exists with same email → update fields, don't duplicate

### `candidate.updated`
- Find by `external_id` OR `email`
- Update all non-empty fields (don't blank existing data if webhook field is empty)
- Touch `updated_at`

### `candidate.deleted`
- Find by `external_id`
- Set `nocodb_deleted = True` (soft flag — field keeps old name for now, rename later)
- Don't hard delete

## Response

```json
// Success
{"status": "ok", "action": "created" | "updated" | "deleted", "candidate_id": 47}

// Error
{"status": "error", "message": "Missing required field: email"}
```

HTTP codes: `200` success, `400` bad payload, `401` unauthorized, `422` validation failed.

## Differences from Current NocoDB Webhook

| Aspect | NocoDB (current) | CF Worker (new) |
|--------|-----------------|-----------------|
| Auth | `X-Webhook-Secret` header | `Authorization: Bearer` |
| Event field | `type` ("records.after.insert") | `event` ("candidate.created") |
| Data shape | `{type, data: {table_id, rows: [...]}}` | `{event, data: {...single candidate}}` |
| Batch | Multiple rows per payload | One candidate per payload |
| Field names | NocoDB column titles ("Full-Name") | Normalized snake_case |
| Delete | Sends row with `Id` only | Sends `external_id` only |

## Migration Path

1. Add new endpoint `/api/webhooks/candidates` alongside existing `/api/webhooks/nocodb`
2. Both coexist during transition (same upsert logic under the hood)
3. Once CF Worker is proven, remove `/api/webhooks/nocodb` and `app/nocodb.py`

## CF Worker Responsibilities

1. Receive Google Form submission (via Apps Script HTTP POST)
2. Validate + normalize field names
3. Write to Neon (INSERT or UPDATE by email)
4. Forward to interview-general webhook (fire-and-forget, retry 3x on failure)
5. On Neon row delete → forward delete event

## Open Questions

- [ ] CV text extraction: does CF Worker download + parse PDF, or does recompute.py still handle that?
- [ ] Bulk backfill: on first deploy, need to seed interview-general from Neon's existing data. One-time script or paginated webhook burst?
- [ ] Rate limit: if 100 forms submit simultaneously, does interview-general need a queue or is sequential webhook fine? (Likely fine — SQLite WAL handles concurrent writes)
