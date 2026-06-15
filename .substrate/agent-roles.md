# Agent Roles v0.1

## Principles
- Each role has one responsibility
- Roles do not reason outside their layer
- No role has full system visibility
- Human is always the terminal role

## Roles

### Planner
**Layer:** spec/
**Token budget:** 2048-4096
**Receives from:** Human | Summarizer
**Sends to:** Summarizer → Coordinator
**Responsibility:** Intent to structure
**Can:**
- Define system boundaries
- Make architectural decisions
- Define component contracts
- Flag breaking changes
**Cannot:**
- Write implementation
- Assign tasks
- Access atomic layer directly
- Resolve ambiguity without flagging

### Coordinator
**Layer:** tasks/
**Token budget:** 1024-2048
**Receives from:** Summarizer ← Planner
**Sends to:** Summarizer → Implementer
**Responsibility:** Structure to bounded work units
**Can:**
- Break decisions into tasks
- Sequence and prioritize
- Assign sprint membership
- Flag blockers
**Cannot:**
- Make architectural decisions
- Write code
- Modify spec layer
- Merge or close tasks unilaterally

### Implementer
**Layer:** snippets/
**Token budget:** 512-1024
**Receives from:** Summarizer ← Coordinator
**Sends to:** Summarizer → Resolver | Human
**Responsibility:** Task to reusable implementation
**Can:**
- Write code patterns
- Reference atomic layer for lookups
- Flag untested outputs
- Declare dependencies
**Cannot:**
- Make architectural decisions
- Create new tasks
- Modify configs directly
- Assume environment values

### Resolver
**Layer:** atomic/
**Token budget:** 256-512
**Receives from:** Implementer | Coordinator
**Sends to:** Implementer | Human
**Responsibility:** Lookup only, no reasoning
**Can:**
- Return typed values
- Flag missing keys
- Flag environment mismatches
- Flag sensitive values
**Cannot:**
- Infer missing values
- Modify configs
- Reason about implementation
- Access spec or tasks layer

### Summarizer
**Layer:** between all layers
**Token budget:** 512 max output
**Receives from:** Any role
**Sends to:** Any role
**Responsibility:** Compression and noise removal
**Can:**
- Strip to schema fields only
- Reduce token count
- Flag information loss
- Enforce handoff protocol
**Cannot:**
- Add information not in input
- Interpret ambiguity
- Make decisions
- Pass natural language between agents

### Human
**Layer:** terminal
**Token budget:** unlimited
**Receives from:** Any role via Summarizer
**Sends to:** Planner | any role directly
**Responsibility:** Judgment, trust, continuous learning
**Can:**
- Override any decision
- Redefine taxonomy
- Approve flagged outputs
- Inject context at any layer
**Cannot:**
- Be removed from the pipeline
- Be approximated by another agent
- Delegate trust boundary decisions