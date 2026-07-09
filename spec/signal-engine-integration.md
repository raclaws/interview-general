---
name: signal-engine-integration-plan
description: Plan to integrate signal engine positioning + keyword search into interview-general candidate views
metadata: 
  node_type: memory
  type: project
  originSessionId: c8247a02-4559-4873-b0fd-fd07f2c9812e
---

## Integration: Signal Engine → Interview-General App

**Goal:** Show signal engine labels on the candidate list/detail pages + power keyword search from CV-extracted skills.

### Part 1: Candidate Positioning Display

Where it shows up: candidate list table + candidate detail page in interview-general.

**Candidate List (table row):**
```
Name | Role | Band | Position | Source | Flags
Hadi | BACKEND_DEV | MARKET P55 | [vs PM_TECH/5-8yr/FSI n=9] | 2 flags
```

Columns to add:
- Salary band (WELL_BELOW / BELOW / MARKET / ABOVE / WELL_ABOVE)
- Percentile (P0-P100)
- Comparison source (which bucket was used + sample size)
- Flag count (clickable → shows flag detail)
- Credibility indicator (HIGH / NORMAL / LOW)

**Candidate Detail Page:**
- Full signal map (all form fields + CV-derived signals with state)
- Company category + tier context
- Cross-signal flags with both interpretations
- Credibility breakdown (costly signals listed)
- CV enrichment section (extra skills, credentials, domains from CV parser)

**Data flow:**
```
NocoDB (form data) → signal_engine.py → JSON output per candidate
                   ↘ cv_cache (text)  → cv_parser.py → structured signals
                                                     ↘ keyword index
```

**Implementation approach:**
- Pre-compute all labels on bulk run, store as JSON per candidate (or SQLite)
- Interview-general reads the pre-computed labels when rendering candidate views
- Re-run engine when new candidates enter (webhook from NocoDB form submission, or periodic batch)

### Part 2: Keyword Search (CV-extracted)

**Source:** cv_parser.py already extracts:
- `skills_explicit` — from SKILLS section
- `skills_contextual` — mentioned in role descriptions
- `domains` — industry/vertical markers
- `ownership_markers` — leadership language

**Search index structure:**
```
candidate_id → {
  skills: ["python", "django", "fastapi", "nlp", "deep learning"],
  domains: ["ai_ml", "banking", "telco"],
  tools: ["jira", "figma", "docker"],
  credentials: ["ITB", "Master"],
  companies: ["PT Assemblr Teknologi Indonesia"],
  company_category: "IMPLEMENTOR",
}
```

**Search modes:**
1. **Skill match:** "python AND aws" → candidates with both
2. **Combo rarity:** "python + rust + go" → highlight candidates with rare combos
3. **Domain filter:** "banking experience" → candidates with FSI company or banking domain marker
4. **Negation:** "NOT freelance" → exclude by employment status

**Implementation approach:**
- Build inverted index from cv_parser output (skill → set of candidate_ids)
- Expose as search endpoint in interview-general backend
- UI: search bar on candidate list page, filters by keyword match
- Boolean logic: AND/OR/NOT on skill/domain/company combinations

### Integration Points with Existing App

Interview-general already has:
- Candidate model + list page (HTMX)
- Pipeline tracking (stages per candidate)
- Interview sessions with scoring

Wire signal engine as:
- New "Signals" tab/section on candidate detail page
- Color-coded band indicator on candidate list
- Search bar using keyword index
- Pre-computed on batch (not real-time) — recruiter sees labels when they open the list

### Open Questions for Implementation
- Store computed signals in SQLite alongside interview-general data, or read from cv_cache JSON?
- Real-time computation on new applications, or batch + refresh?
- How to handle the 66% without company category — show "generic comparison" explicitly or omit the source?

**Why:** recruiter should see positioning + flags at a glance when scanning candidates, without opening each CV. Keyword search enables "find me all Python+AWS candidates from banking background" without manual filtering.

**How to apply:** next session, wire the pre-computed signal engine output into interview-general's candidate views. Start with the list table (band + percentile column), then detail page, then search.
