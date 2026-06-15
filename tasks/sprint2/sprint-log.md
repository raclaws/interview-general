# Sprint Log v0.1

## Invariants
- Append-only, never edit existing rows
- Timestamp is ISO8601 UTC
- Event must be from valid enum
- Role must match agent-roles.md
- One row per event, no batching

## Events
chain_start | role_complete | summarize | gate_pass | gate_fail | human_intervention | sprint_complete | error

## Log

| timestamp | event | role | detail |
|-----------|-------|------|--------|