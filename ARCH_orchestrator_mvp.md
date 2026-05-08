# ARCH: Orchestrator (MVP)

## Purpose

Minimal activation loop that wires all MVP modules into a running system. Handles cron-triggered activations, bootstrap awareness, inbound message dispatch, and graceful shutdown. This is the subset of ARCH_orchestrator.md required to satisfy the MVP Definition in PROJECT.md.

**Deferred to full Orchestrator (post-MVP):** lateral-freedom budget, tension-responsive scheduling, ambient context assembly, budget banking/quiet-day ratios, debt accounting, cool-down windows, under-engaged material resurfacing, custom ambient streams, task arbitration.

## Relationship to ARCH_orchestrator.md

This spec is a strict subset. Every type, method, and behavior defined here is forward-compatible with the full Orchestrator contract. When the full Orchestrator is built, this MVP implementation either gets extended in place or replaced — no downstream modules change.

## Public API

### Types

```python
@dataclass
class MVPOrchestratorConfig:
    schedule: list[ScheduleEntry]                   # cron-based activation schedule
    generation_prompt: GenerationPrompt             # default prompt for scheduled generation
    attention_filter_config: AttentionFilterConfig   # shared filter config for ingestion
    distillation_config: DistillationConfig          # shared distillation config
    generator_config: GeneratorConfig               # shared generator config
    router_config: RouterConfig                     # output routing config
    log_path: Path | None = None                    # activation log file (JSON lines), None = no log

@dataclass
class ScheduleEntry:
    task_type: str                                  # "ingestion", "generation", "distillation", "decay"
    cron: str                                       # cron expression (e.g., "0 */4 * * *")
    enabled: bool = True

@dataclass
class ActivationResult:
    task_type: str
    success: bool
    outputs_delivered: int                          # number of GeneratorOutputs routed to Gateway
    error: str | None = None                        # error message if success=False
    duration_ms: int = 0                            # wall-clock time
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

### ModuleRefs

```python
@dataclass
class ModuleRefs:
    memory_store: MemoryStore
    attention_filter: AttentionFilter
    source_ingestion: SourceIngestion
    distillation_engine: DistillationEngine
    generator: Generator
    gateway: Gateway
```

No `feedback_collector` or `explorer` — MVP does not require them.

### Constructor

- **Signature:** `MVPOrchestrator(modules: ModuleRefs, config: MVPOrchestratorConfig)`
- **Validation:**
  - `config.schedule` must be non-empty
  - Each `ScheduleEntry.task_type` must be one of: `"ingestion"`, `"generation"`, `"distillation"`, `"decay"`
  - Each `ScheduleEntry.cron` must be a valid 5-field cron expression
  - All `ModuleRefs` fields must be non-None
- **Errors:** `ConfigError` on validation failure

### start

- **Signature:** `start() -> None`
- **Behavior:** Blocks. Registers cron entries, starts the Gateway listener for inbound messages, enters the main loop. Dispatches activations when cron fires. Exits when `stop()` is called or SIGTERM is received.
- The main loop is a simple sleep-poll: check which cron entries have fired since last check, run them sequentially, sleep until next check.
- **Gateway listener:** On inbound message, dispatches a `respond` activation inline (not scheduled). If the system is in bootstrap mode (no personality files), responds with a configurable "not ready" message or silently drops.

### stop

- **Signature:** `stop() -> None`
- **Behavior:** Signals the main loop to exit after the current activation completes. Does not interrupt in-progress activations.

### trigger

- **Signature:** `trigger(task_type: str) -> ActivationResult`
- **Behavior:** Manual single-activation trigger for testing and debugging. Runs the specified task type synchronously and returns the result. Respects bootstrap mode.

## Activation Types

| Type | What it does | Bootstrap behavior |
|------|-------------|-------------------|
| `ingestion` | `source_ingestion.poll()` → `attention_filter.filter_content()` → `memory_store.store_note()` for accepted fragments | Runs normally (prompt-criteria-only filtering at zero density) |
| `distillation` | `distillation_engine.check_gates()` → if ready: `distill_t1_to_t2()` and/or `distill_t2_to_t3()` | Runs normally — produces first personality files |
| `generation` | `generator.generate()` → `route()` → `gateway.send()` | **Skipped** — catches `EmptyPersonalityError`, logs, no output |
| `decay` | `memory_store.run_decay()` | Runs normally |
| `respond` | `generator.respond(message)` → `route()` → `gateway.send()` | **Skipped** — catches `EmptyPersonalityError`, drops message |

## Activation Lifecycle (MVP)

Every activation follows this sequence:

```
1. Trigger         cron fire / inbound message / manual trigger()
       ↓
2. Bootstrap check  if task requires personality: check memory_store.get_personality_context()
                    if empty: log skip, return early
       ↓
3. Execute task     dispatch to module(s) per activation type
       ↓
4. Route outputs    if generation/respond: GeneratorOutput → route() → Gateway
       ↓
5. Log              append ActivationResult to log file (if configured)
```

No ambient context assembly, no lateral check, no budget accounting.

### Ingestion Activation Detail

```python
# Pseudocode — not the implementation, but the wiring contract
results = source_ingestion.poll()                    # poll all enabled adapters
all_items = flatten(r.items for r in results)         # collect ContentItems
if not all_items:
    return ActivationResult(task_type="ingestion", success=True, outputs_delivered=0)

filter_result = attention_filter.filter_content(all_items, config.attention_filter_config)

for fragment in filter_result.accepted:
    note_input = NoteInput(
        title=fragment_title(fragment),
        content=fragment.content,
        tier=1,
        tags=fragment_tags(fragment),
        importance=fragment.importance_score,
        unresolvedness=fragment_unresolvedness(fragment),
    )
    memory_store.store_note(note_input)

return ActivationResult(task_type="ingestion", success=True, outputs_delivered=0)
```

The ingestion activation is the primary content pipeline. It does not produce Generator outputs — `outputs_delivered` is always 0 for ingestion.

### Distillation Activation Detail

```python
gates = distillation_engine.check_gates(config.distillation_config)
if not gates.ready:
    return ActivationResult(task_type="distillation", success=True, outputs_delivered=0)

if gates.t1_to_t2_ready:
    distillation_engine.distill_t1_to_t2(config.distillation_config)

if gates.t2_to_t3_ready:
    distillation_engine.distill_t2_to_t3(config.distillation_config)

return ActivationResult(task_type="distillation", success=True, outputs_delivered=0)
```

Gate evaluation and distillation both handle their own locking. The orchestrator does not manage the consolidation lock.

### Generation Activation Detail

```python
try:
    output = generator.generate(
        prompt=config.generation_prompt,
        ambient={},                                   # MVP: empty ambient context
        config=config.generator_config,
    )
except EmptyPersonalityError:
    # Bootstrap mode — no personality files yet
    return ActivationResult(task_type="generation", success=True, outputs_delivered=0)

delivery = route(output, config.router_config, gateway)
delivered = 1 if (delivery and delivery.success) else 0

return ActivationResult(task_type="generation", success=True, outputs_delivered=delivered)
```

### Respond Activation Detail

```python
# Triggered by Gateway listener callback, not cron
try:
    output = generator.respond(
        message=inbound_message,
        ambient={},
        config=config.generator_config,
    )
except EmptyPersonalityError:
    return ActivationResult(task_type="respond", success=True, outputs_delivered=0)

delivery = route(output, config.router_config, gateway)
delivered = 1 if (delivery and delivery.success) else 0

return ActivationResult(task_type="respond", success=True, outputs_delivered=delivered)
```

### Decay Activation Detail

```python
memory_store.run_decay()
return ActivationResult(task_type="decay", success=True, outputs_delivered=0)
```

## Error Handling

- **Module errors during activation:** Caught at the activation level. The activation returns `success=False` with the error message. The main loop continues — one failed activation does not stop the system.
- **Distillation lock contention:** `DistillationLockError` is caught and treated as a skip (success=True, no work done). Another activation will retry later.
- **`InsufficientDataError` / `NoPatternDataError`:** Caught and treated as a skip. Normal during early operation when data volume is low.
- **Gateway errors during output routing:** Delivery failures are captured in `DeliveryResult.success=False`. The activation still succeeds — the output was generated, delivery just failed.
- **Unhandled exceptions:** Logged, activation returns `success=False`, main loop continues.

## State

- **Schedule state:** Active cron entries, next-fire times. In-memory, derived from config. Lost on restart (re-derived from config).
- **Activation log:** Append-only JSON lines file at `config.log_path`. Each line is a serialized `ActivationResult`. Used for monitoring and debugging, not for recovery.
- **No budget tracking, no interaction tracking, no banked budget.** MVP does not implement these — the system runs at constant cadence regardless of tension or quiet periods.

All durable state lives in Memory Store (vault, index, distillation metadata). The MVP Orchestrator is stateless across restarts except for the activation log.

## Bootstrap Detection

```python
def _is_bootstrap(self) -> bool:
    ctx = self.modules.memory_store.get_personality_context()
    return len(ctx.personality_files) == 0
```

Bootstrap mode is checked per-activation, not cached. The system transitions out of bootstrap automatically when the first `distill_t2_to_t3` run produces personality files.

## Deployment

Runs as a systemd service inside the `claude-code` Incus container (development phase) or a dedicated container (production phase), per PROJECT.md Deployment section.

```ini
# phosphene.service
[Unit]
Description=Phosphene MVP Orchestrator
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 -m phosphene.orchestrator
WorkingDirectory=/path/to/phosphene
MemoryMax=512M
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

## Cron Expression Format

Standard 5-field cron: `minute hour day-of-month month day-of-week`. Evaluated using the `croniter` library (add to `.python_deps`). Examples:

| Expression | Meaning |
|-----------|---------|
| `0 */4 * * *` | Every 4 hours |
| `0 10 * * *` | Daily at 10:00 |
| `0 3 * * *` | Daily at 03:00 |
| `0 0 1 * *` | First of each month |

## Default Schedule

```python
DEFAULT_SCHEDULE = [
    ScheduleEntry("ingestion",    "0 */4 * * *"),   # every 4 hours
    ScheduleEntry("distillation", "30 */4 * * *"),   # 30 min after ingestion
    ScheduleEntry("generation",   "0 10 * * *"),     # daily at 10am
    ScheduleEntry("decay",        "0 3 * * *"),      # daily at 3am
]
```

Distillation is scheduled frequently but self-gates — `check_gates()` returns `ready=False` unless enough new material has accumulated. Running the schedule entry is cheap when gates don't pass.

## What This Does NOT Do

Explicit list of full-Orchestrator features excluded from MVP:

- **Lateral freedom** — no free-play budget, no lateral check after task completion
- **Tension-responsive scheduling** — constant cadence, no frequency adjustment
- **Ambient context assembly** — Generator receives `{}` as ambient context
- **Budget tracking** — no token budgets, no quiet-day ratios, no banking
- **Debt accounting** — no lateral debt concept
- **Cool-down windows** — no rate limiting between outputs
- **Task arbitration** — no min-task-completion, no preemption classes
- **Under-engaged resurfacing** — no post-decay surfacing of neglected notes
- **Feedback Collector integration** — no feedback loop closure
- **Explorer integration** — no link-following
- **Custom ambient streams** — no environmental data injection

## Implementation Phases

### Phase 1: Contract and cron loop
- Public types, config validation, ModuleRefs validation
- Cron evaluation (croniter integration)
- Main loop: sleep-poll, dispatch, log
- `start()` / `stop()` / `trigger()` lifecycle
- No module wiring — dispatch stubs that return empty ActivationResults

### Phase 2: Activation wiring
- Ingestion activation: poll → filter → store
- Distillation activation: check_gates → distill
- Generation activation: generate → route → send (with bootstrap skip)
- Decay activation: run_decay
- Respond activation: Gateway listener → generate → route → send

### Phase 3: Integration hardening
- Error isolation per activation
- Activation logging
- Bootstrap detection and transition
- Restart recovery (re-derive schedule, resume from config)
- End-to-end test with fake modules proving the full ingestion → distillation → generation → delivery path
