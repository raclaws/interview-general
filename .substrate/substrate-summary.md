# Substrate v0.1 - Meta Summary

## What This Is
A project-agnostic cognitive substrate for LLM agent pipelines.
Structure is stable. Semantics are project-specific. Process is explicit.

## Core Principles
- Natural language is human-facing only
- Structured handoffs (JSON) between all agents
- Context is designed, not assumed
- Human is non-optional in the pipeline
- Information loss is visible, never silent

## Layers
| Layer | Budget | Role | Purpose |
|-----------|---------------|-------------|----------------------------|
| spec/ | 2048-4096 | Planner | Intent to structure |
| tasks/ | 1024-2048 | Coordinator | Structure to work units |
| snippets/ | 512-1024 | Implementer | Task to implementation |
| atomic/ | 256-512 | Resolver | Lookup only, no reasoning |

## Flow
Human → Planner → Summarizer → Coordinator → Summarizer → Implementer ↔ Resolver → Summarizer → Human

## Hard Constraints
1. No natural language between agents
2. No role reasons outside its layer
3. Resolver never infers
4. Summarizer output always smaller than input
5. Breaking changes always return to Human
6. Junk drawer folders forbidden
7. Human cannot be removed from pipeline

## LLM Operational Notes
- You are a frozen approximation operating within defined context boundaries
- Confidence is a float, not a feeling
- When uncertain, set flag - do not infer
- Token budget is a ceiling, not a target
- If input doesn't fit schema, reject and flag - do not reinterpret