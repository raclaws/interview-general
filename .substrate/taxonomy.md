# Taxonomy v0.1

## Principles
- Structure is stable, semantics are project-specific
- Context budget reflects information density, not importance
- Natural language is human-facing only
- Handoffs are structured, typed, explicit

## Layers

### spec/ (2048-4096 tokens)
**Purpose:** Intent and constraints, not implementation
**Contains:** What the system is, why decisions were made
**Invariants:**
- architecture/ = system boundaries and rationale
- api/ = contracts between components
- components/ = behavioral definitions, not code
**Handoff type:** JSON with explicit decision fields
**Agent role:** Planner

### tasks/ (1024-2048 tokens)
**Purpose:** Bounded units of work with clear completion state
**Contains:** What needs to happen, in what order
**Invariants:**
- sprint*/ = time-bounded, sequenced
- backlog/ = unsequenced, unprioritized candidates
**Handoff type:** JSON with status enum
**Agent role:** Coordinator
**Status enum:** [pending, active, blocked, done]

### snippets/ (512-1024 tokens)
**Purpose:** Reusable implementations with known behavior
**Contains:** Code patterns, not business logic
**Invariants:**
- components/ = UI or functional units
- hooks/ = stateful behavior patterns
- utilities/ = pure functions, no side effects
**Handoff type:** JSON with dependency fields
**Agent role:** Implementer

### atomic/ (256-512 tokens)
**Purpose:** Lookup, not reasoning
**Contains:** Values, not logic
**Invariants:**
- errors/ = typed, coded, no ambiguity
- configs/ = environment-bounded values
- env-vars/ = external dependencies declaration
**Handoff type:** Direct reference, no summarization needed
**Agent role:** Resolver

## Handoff Protocol
- Layer N output → summarizer → Layer N+1 input
- Summarizer strips to schema fields only
- No natural language between layers
- Natural language only at human interface layer

## Invariant Rules
1. Components in spec/ = contracts
2. Components in snippets/ = implementations
3. Same term at different layers = different abstraction, must be prefixed if referenced cross-layer
4. Junk drawer folders forbidden - if it doesn't fit, taxonomy needs updating not a new misc/ folder
5. Token budgets are ceilings, not targets

**The last rule is important** - junk drawers are where taxonomies die.