# INS ATS — Component Inventory

## Models (app/models.py)

| Model | Table | Purpose |
|-------|-------|---------|
| AdminUser | admin_users | Auth (username, password, session_version) |
| BusinessUnit | business_units | Organization units (name, head, recruiter, portal_token) |
| Job | jobs | Open positions (position, level, BU, headcount, salary, status) |
| Candidate | candidates | People (name, email, skills, salary, CV link, nocodb_id) |
| CandidatePipeline | candidate_pipelines | Candidate × Job junction (stage tracking) |
| InterviewSession | sessions | Interview scheduling (template, candidate, pipeline) |
| SessionInterviewer | session_interviewers | Per-interviewer token + status |
| Response | responses | Submitted interview answers |
| ResponseScore | response_scores | Per-dimension scores within a response |
| Template | templates | Interview question templates (HR, Culture, custom) |
| TemplateSection | template_sections | Dimensions within a template |
| PipelineScore | pipeline_scores | Aggregated scorecard per pipeline |
| TestAssignment | test_assignments | External test links sent to candidates |
| ReviewBatch | review_batches | Grouped test submissions for scoring |
| ReviewScore | review_scores | Individual test scores |
| Comment | comments | Comments + activity trail (entity_type polymorphic) |
| Task | tasks | Lightweight to-do tied to job or pipeline |
| ManpowerRequest | manpower_requests | BU headcount requests (portal-submitted) |
| OfferLetter | offer_letters | Generated offer documents |
| CandidateSignal | candidate_signals | Pre-computed signal engine data (band, skills, flags) |
| Setting | settings | Key-value config (LLM, NocoDB, webhook secret) |
| TableView | table_views | Saved list view configs (filters, sort, group) |
| ManagedPosition | managed_positions | Controlled position vocabulary |
| ManagedLevel | managed_levels | Controlled level vocabulary |
| ManagedJobType | managed_job_types | Controlled job type vocabulary |
| ReportHistory | report_history | Cached LLM report outputs |

## Routes (app/routes/)

| File | Prefix | Pages/Endpoints |
|------|--------|-----------------|
| admin.py | / | Dashboard, login/logout, session CRUD, bulk actions, restore/purge |
| jobs.py | /job, /jobs | Job CRUD, add candidate, generate post |
| candidates.py | /candidate, /candidates | Candidate CRUD, pipeline mgmt, scorecard, test assign |
| tasks.py | /tasks | Task CRUD, status change, inline section |
| settings.py | /settings | LLM, BU, positions, levels, job-types, NocoDB, offer config, account |
| interview.py | /i | Token-gated interview form submission |
| test_portal.py | /t | Token-gated test submission |
| review.py | /r | Token-gated batch review portal |
| portal.py | /portal | BU portal (requests, jobs, pipelines, comments) |
| requests.py | /requests | Admin manpower request management |
| offers.py | /offers | Offer letter generation + preview |
| reports.py | /reports | LLM-powered reports (general, job, pipeline) |
| sync.py | /sync | REST hydrate + WebSocket change stream |
| webhooks.py | /api/webhooks | NocoDB webhook receiver |
| docs.py | /guide | User documentation (10 pages, Bahasa) |
| perf.py | /perf | Performance monitoring endpoints |

## Backend Modules (app/)

| File | Purpose |
|------|---------|
| main.py | FastAPI app factory, middleware, route registration |
| models.py | All SQLModel schemas |
| database.py | SQLite engine, migrations, WAL mode, table creation |
| auth.py | bcrypt hashing, cookie sessions, rate limiting, session_version |
| llm.py | OpenAI-compatible client, summarization, settings helpers |
| nocodb.py | NocoDB API client (search, fetch, bulk import, upsert) |
| activity.py | record_activity() with FK-walk propagation |
| helpers.py | Shared utilities (render_gone, compute_pipeline_scores) |
| offers.py | Salary calculation module (configurable factors) |
| reports.py | Report generation logic |
| export.py | PDF export (pipeline, scorecard) |
| seed.py | Template + managed data seeding, legacy migration |
| mcp_server.py | FastMCP server (12 tools: sessions, jobs, pipelines, candidates, tasks) |
| cli.py | CLI commands (create-admin) |

## Templates

### Layouts
| File | Purpose |
|------|---------|
| base.html | Minimal layout (public portals) |
| base_app.html | Admin layout (sidebar, topbar, shortcuts) |
| docs/layout.html | Guide documentation layout |
| portal/layout.html | BU portal layout |

### List Pages (sync-list)
| File | Entity | Columns |
|------|--------|---------|
| candidates_list.html | Candidates | Person, position+skills, band pill, counts, action, date |
| jobs_list.html | Jobs | Title, BU, status, headcount, pipeline count, date |
| pipelines_list.html | Pipelines | Candidate, job, stage, score, session count, date |
| sessions_list.html | Sessions | Candidate, template, status, interviewers, date |
| review_batches_list.html | Review Batches | Position, reviewer, scored/total, date |
| tasks/list.html | Tasks | Title+entity, status, priority, due date, assigned |

### Detail Pages
| File | Entity |
|------|--------|
| candidate_detail.html | Candidate (profile, signals, pipelines, comments, activity) |
| job_detail.html | Job (info, links, pipelines, tasks, comments, activity) |
| pipeline_detail.html | Pipeline (stage, scorecard, sessions, tests, tasks, comments) |
| session_detail.html | Session (interviewers, responses, summary) |
| tasks/detail.html | Task (inline-edit fields, linked entity) |
| template_detail.html | Template (sections, questions) |
| requests/detail.html | Manpower request (approve/reject) |

### Forms
| File | Purpose |
|------|---------|
| candidate_new.html | New candidate |
| candidate_edit.html | Edit candidate |
| job_form.html | New/edit job |
| session_new.html | New interview session |
| session_edit.html | Edit session |
| pipeline_new.html | New pipeline |
| tasks/form.html | New task (entity picker) |
| test_new.html | Assign test |
| review_batch_new.html | New review batch |
| offers/form.html | Generate offer letter |
| jobs/post_form.html | Generate LinkedIn post |
| portal/form.html | BU manpower request |

### Public Portals (token-gated)
| File | Purpose |
|------|---------|
| interview_form.html | Interviewer fills scores |
| interview_done.html | Submission confirmation |
| test_portal.html | Test submission form |
| test_done.html | Test submission confirmation |
| test_expired.html | Expired test link |
| test_password.html | Password-gated test |
| review_portal.html | Batch review scoring |
| portal/home.html | BU portal home (tabs) |
| portal/job_detail.html | BU view of job pipelines |
| portal/pipeline_detail.html | BU view of pipeline + comments |

### Settings Tabs
| File | Tab |
|------|-----|
| settings_layout.html | Shell (nav + content area) |
| settings_llm.html | LLM config |
| settings_bu.html | Business Units |
| settings_list.html | Positions / Levels / Job Types |
| settings_nocodb.html | NocoDB Sync |
| settings_offer_config.html | Offer Calculation |
| settings_account.html | Password change |

### Partials
| File | Used in |
|------|---------|
| partials/peek_panel.html | Global (comments side panel) |
| partials/pipeline_list.html | Candidate detail |
| partials/trail_item.html | Activity/comment trail |
| partials/summary_block.html | Session detail |
| partials/report_result.html | Reports page |
| partials/report_history.html | Reports page |
| partials/review_row.html | Review portal |
| partials/review_score_form.html | Review portal |
| partials/job_links.html | Job detail |

### Guide Documentation
| File | Topic |
|------|-------|
| docs/home.html | Landing page |
| docs/mulai.html | Getting started |
| docs/jobs.html | Managing jobs |
| docs/kandidat.html | Managing candidates |
| docs/pipeline.html | Pipeline management |
| docs/tugas.html | Tasks |
| docs/wawancara.html | Interviews & scoring |
| docs/portal.html | BU portal |
| docs/laporan.html | Reports |
| docs/pengaturan.html | Settings |
| docs/mcp.html | MCP agent tools |

### Other
| File | Purpose |
|------|---------|
| dashboard.html | Admin dashboard |
| login.html | Login page |
| 404.html | Not found |
| gone.html | Deleted entity |
| recently_deleted.html | Soft-deleted items (30-day purge) |
| session_hr_conflict.html | HR session limit conflict |
| pipeline_score.html | Scorecard view |
| offers/letter.html | Offer letter (print template) |
| offers/result.html | Offer preview + copy |
| jobs/post_result.html | LinkedIn post preview + copy |
| reports.html | Reports shell |
| reports/general.html | General report |
| reports/job.html | Job report |
| reports/pipeline.html | Pipeline report |
| export/pipeline_pdf.html | PDF export template |
| export/scorecard_pdf.html | PDF export template |

## Static Assets

| File | Purpose |
|------|---------|
| style.css | Full CSS (variables, layout, components, dark mode) |
| cells.js | Cell render vocabulary (text, badge, band, person, link, select, etc.) |
| sync-list.js | IDB + WebSocket sync engine (filter, sort, group, search, collapse) |
| sync-list-v2.js | Legacy/alternate sync implementation |
| shortcuts.js | Keyboard shortcuts (vim-style navigation) |

## External Integrations

| System | Purpose | Config |
|--------|---------|--------|
| NocoDB | Candidate data source | NOCODB_BASE_URL, API_KEY, TABLE_ID |
| OpenAI-compatible LLM | Summaries, reports, post generation | LLM_BASE_URL, API_KEY, MODEL |
| Signal Engine | Salary positioning + CV skills | recompute.py (candidate-search/) |
| MCP Server | Agent tool access | app/mcp_server.py |
