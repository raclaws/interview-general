# Context Budgets v0.1

## Layer Token Ceilings
| Layer | Max Tokens | Purpose |
|-------|------------|---------|
| **spec/** | 4096 | Architectural decisions, system boundaries |
| **tasks/** | 2048 | Bounded work units, acceptance criteria |
| **snippets/** | 1024 | Reusable code patterns, implementations |
| **atomic/** | 512 | Lookup values only, no reasoning |

## Budget Enforcement Rules
1. **Ceilings, not targets** - Efficiency is rewarded
2. **Summarizer must reduce** - Output always smaller than input
3. **Human review on overflow** - Any layer exceeding its budget triggers review
4. **Progressive compression** - 4096 → 2048 → 1024 → 512 enforced between layers

## Token Counting Method
- Primary: Target model's tokenizer
- Fallback: cl100k_base (GPT-4 tokenizer)
- Rough estimate beats wrong precision
- Revisit when real budget violations occur

## Compression Priority (Summarizer)
When hitting token limits, drop in order:
1. notes (optional commentary)
2. rationale_ref (reference to full rationale)
3. assumptions (contextual assumptions)
4. dependencies (cross-references)

**Never drop:** decision, status, flags, confidence