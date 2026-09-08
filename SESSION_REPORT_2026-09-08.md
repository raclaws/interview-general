# Session Report — NocoDB → Neon Migration

**Date:** 2026-09-08
**Branch:** `nocodb-to-neon` → merged to `master`
**PR:** [#14](https://github.com/raclaws/interview-general/pull/14)

---

## Objective

Replace NocoDB (external candidate data source) with Neon Postgres as the canonical candidate store for INS ATS. Keep SQLite as the operational database. Add webhook sync so new Google Form submissions appear in INS ATS automatically.

---

## Architecture

```
Before:
  Google Form → Apps Script → candidate-ingest CF Worker → Hyperdrive → Neon
                            → POST /api/webhooks/nocodb (NocoDB format) → INS ATS

After:
  Google Form → Apps Script → candidate-ingest CF Worker → Hyperdrive → Neon
                            → POST /api/webhooks/candidates (Neon format) → INS ATS
```

INS ATS also has direct Neon access for admin search, fetch, and bulk import via `app/neon.py` (asyncpg).

---

## Files Changed

**24 files, +608 / −530 lines**

### New Files
| File | Purpose |
|------|---------|
| `app/neon.py` | asyncpg client — `search_candidates()`, `fetch_candidate()`, `bulk_import_candidates()`, `upsert_candidate_from_neon()`, `close_pool()` |
| `templates/settings_neon.html` | Neon Sync settings page (connection status, import, webhook config) |

### Deleted Files
| File | Reason |
|------|--------|
| `app/nocodb.py` | NocoDB API client — replaced by `app/neon.py` |
| `templates/settings_nocodb.html` | NocoDB settings page — replaced by Neon page |

### Modified Files
| File | Changes |
|------|---------|
| `app/models.py` | Added `external_id` column to `Candidate` and `CandidateSignal` |
| `app/database.py` | Added migration entries for `external_id` |
| `app/main.py` | Added shutdown handler to close asyncpg pool |
| `app/routes/webhooks.py` | Replaced `/nocodb` endpoint with `/candidates` (Bearer auth, new payload format, correct action tracking) |
| `app/routes/admin.py` | Added `entry_mode == "neon"` for session creation, `/api/neon-search` endpoint; removed NocoDB mode |
| `app/routes/candidates.py` | Added `mode == "neon_import"`, `mode == "existing"`; removed NocoDB modes |
| `app/routes/jobs.py` | Added `mode == "neon"` add-candidate flow; removed NocoDB mode |
| `app/routes/settings.py` | Added `/settings/neon` routes (status, import, secret); removed NocoDB routes |
| `app/mcp_server.py` | Switched import from `app.nocodb` to `app.neon` |
| `templates/candidate_new.html` | Neon import radio + search picker; removed NocoDB radio |
| `templates/job_detail.html` | Neon import radio + search JS; removed NocoDB radio |
| `templates/settings_layout.html` | Added Neon Sync tab; removed NocoDB tab |
| `templates/docs/home.html` | "NocoDB" → "Neon" |
| `templates/docs/kandidat.html` | "NocoDB" → "Neon" |
| `templates/docs/mulai.html` | "NocoDB" → "Neon" |
| `.env` | `NOCODB_*` → `NEON_DATABASE_URL`, `ADMIN_PASSWORD=admin` |
| `.env.example` | `NOCODB_*` → `NEON_DATABASE_URL` |
| `.env.staging` | `NOCODB_*` → `NEON_DATABASE_URL` |
| `requirements.txt` | Added `asyncpg>=0.30.0` |
| `.dockerignore` | Added `cookies.txt`, `*.log` |
| `.gitignore` | Added `*.db-shm`, `*.db-wal`, `cookies.txt`, `static/offers/`, `static/reports/` |

---

## Code Review Fixes Applied

| Issue | Fix |
|-------|-----|
| Webhook always returned `"action": "updated"` | Check existing candidate before upsert, set correct action |
| No pool shutdown → connection leak | Added `close_pool()` + `@app.on_event("shutdown")` in main.py |
| Bulk import opened DB session per row (N+1) | Pre-load existing emails into a set, single query |

---

## Testing Results

| Test | Result |
|------|--------|
| Neon search (`search_candidates`) | ✅ 3 results for "alief" |
| Neon fetch (`fetch_candidate`) | ✅ Correct candidate data |
| Neon bulk import (`bulk_import_candidates`) | ✅ 3,462 candidates imported |
| Pool shutdown (`close_pool`) | ✅ Clean close |
| Pool lazy re-init | ✅ Works after close |
| Webhook endpoint (`POST /api/webhooks/candidates`) | ✅ Ready |
| Docker compatibility | ✅ No Dockerfile changes needed |
| `.gitignore` DB protection | ✅ Prod + staging SQLite covered |

---

## Infrastructure Updates

### CF Worker: `candidate-ingest`
- Updated `src/index.js`: added `RETURNING id` to INSERT, new webhook payload format (`event`, `data.external_id`, `Authorization: Bearer`), new env vars (`ATS_WEBHOOK_URL`, `ATS_WEBHOOK_SECRET`)
- Updated `wrangler.toml`: added env vars
- Redeployed to `https://candidate-ingest.raka-feisal.workers.dev`

### CF Worker: `cf-worker-neon` (redundant)
- Deleted — functionality folded into `candidate-ingest`

---

## Credentials & Secrets

| Key | Value |
|-----|-------|
| Admin login | `admin` / `admin` |
| Neon DB | `ep-aged-river-atm1y4v1-pooler` (3,462 candidates) |
| Webhook secret | `J82FdPzpWCINRyrKUgEYuBXAiDaoGn9t` |
| CF account | `Raka.feisal@gmail.com's Account` (`66bc302ceeffd5db7f4e1c191467acd8`) |

---

## Deploy Checklist (for VPS)

1. `git pull` (on master)
2. Update `.env`: set `NEON_DATABASE_URL`
3. `docker compose up -d --build`
4. Open Settings → Neon Sync → paste webhook secret `J82FdPzpWCINRyrKUgEYuBXAiDaoGn9t`
5. Click "Import All Candidates" to backfill `external_id` for existing candidates
6. Verify: search a candidate via Neon import in the UI

---

## Intentional Legacy References (not removed)

| Reference | Reason |
|-----------|--------|
| `Candidate.nocodb_id` | Legacy column, preserved for backward compat |
| `Candidate.nocodb_deleted` | Soft-delete flag, still used by new webhook |
| `CandidateSignal.nocodb_id` | Legacy column, alongside new `external_id` |
| `sync.py` / `mcp_server.py` filter `nocodb_deleted == False` | Correct soft-delete behavior |

---

## Token Cost

~180k tokens consumed across analysis, implementation, review, and testing across multiple model calls.
