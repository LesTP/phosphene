# ARCH: Orchestrator

## Purpose
Top-level wiring and activation lifecycle manager. Connects all Phosphene modules, manages scheduled and triggered activations, assembles ambient context, allocates lateral-freedom budgets, and routes outputs. Subsumes the Scheduler role (ARCHITECTURE.md lists them at the same implementation order). The Orchestrator is the entry point for running Phosphene — it is not consumed by other modules.

## Public API

### Types

```python
@dataclass
class OrchestratorConfig:
    schedule: list[ScheduleEntry]                   # cron-based activation schedule
    lateral_budget_ratio: float = 0.15              # fraction of activation token budget for lateral movement
    tension_threshold: float = 0.7                  # unresolvedness level triggering dedicated free-play activations
    tension_check_interval: timedelta = timedelta(hours=6)  # how often to check tension for free-play triggers
    base_activation_budget: int = 8000              # token budget per activation (excluding lateral)
    quiet_day_budget_ratio: float = 0.6             # budget ratio on low-tension days (remainder banked)
    high_tension_budget_multiplier: float = 1.5     # budget multiplier when unresolved tension is high
    ambient_streams: list[AmbientStreamDef] = field(default_factory=list)  # custom ambient data sources

@dataclass
class ScheduleEntry:
    task_type: str                                  # activation type (see Activation Types table)
    cron: str                                       # cron expression (e.g., "0 */4 * * *" = every 4 hours)
    enabled: bool = True
    config_override: dict | None = None             # per-task config overrides (e.g., different model tier)

@dataclass
class AmbientStreamDef:
    name: str                                       # identifier (e.g., "weather", "time_of_day")
    source: Callable[[], dict]                      # callable returning key-value data
    description: str                                # what this stream represents

@dataclass
class AmbientContext:
    timestamp: datetime
    day_of_week: str
    time_of_day: str                                # "morning", "afternoon", "evening", "night"
    budget_remaining: int                           # tokens remaining today
    budget_trend: str                               # "increasing", "stable", "decreasing", "critical"
    activation_count_today: int
    time_since_last_interaction: timedelta | None    # None if no human interaction yet
    memory_metrics: DensityMetrics                  # from memory_store.get_density_metrics()
    custom_streams: dict[str, dict]                 # from AmbientStreamDef sources

@dataclass
class ModuleRefs:
    memory_store: MemoryStore                       # ARCH_memory_store.md
    attention_filter: AttentionFilter               # ARCH_attention_filter.md
    distillation_engine: DistillationEngine         # ARCH_distillation.md
    source_ingestion: SourceIngestion               # adapters for content sources (ARCH pending)
    generator: Generator                            # prompted and free-play generation (ARCH pending)
    output_router: OutputRouter                     # maps outputs to platforms (ARCH pending)
    gateway: Gateway                                # multi-platform message bus (ARCH pending)
    feedback_collector: FeedbackCollector            # normalizes feedback signals (ARCH pending)
    explorer: Explorer | None = None                # link-following, optional (ARCH pending)

@dataclass
class ActivationResult:
    task_type: str
    task_completed: bool
    outputs: list[GeneratorOutput]                  # all outputs produced (prompted + lateral)
    lateral_movement: bool                          # whether the system deviated from the scheduled task
    lateral_output: GeneratorOutput | None          # output from lateral movement (if any)
    budget_used: int                                # tokens consumed
    lateral_budget_used: int                        # tokens consumed by lateral movement
    duration_ms: int                                # wall-clock time
    ambient_context: AmbientContext                 # context snapshot for this activation

# Referenced from ARCHITECTURE.md Core Objects (ARCH files pending for these modules)
@dataclass
class GeneratorOutput:
    content: str
    intent_tag: str                                 # "synthesis", "provocation", "question", "aesthetic",
                                                    # "internal_note", "log_surfacing", "subscription_proposal"
    output_mode: str                                # "prompted", "free_play", "lateral", "response"
    importance_score: float                         # [0.0, 1.0]
    is_lateral: bool                                # True if produced by lateral movement, not the scheduled task
```

### Constructor

- **Signature:** `Orchestrator(modules: ModuleRefs, config: OrchestratorConfig)`
- **Parameters:**
  - modules: ModuleRefs — references to all Phosphene modules
  - config: OrchestratorConfig — schedule, budgets, tension thresholds, ambient streams
- **Errors:**
  - `ConfigError` — invalid cron expression, budget values out of range, or missing required modules

### start

- **Signature:** `start() -> None`
- **Parameters:** none
- **Returns:** None. Blocks — runs the scheduling loop until `stop()` is called or the process is terminated.
- **Behavior:**
  1. Registers cron entries from `config.schedule`.
  2. Starts the tension-check loop (polls `memory_store.get_density_metrics()` at `tension_check_interval`).
  3. Starts the Gateway listener for inbound messages.
  4. Enters the main loop: waits for the next trigger (cron, tension threshold, or inbound message) and dispatches to `run_activation`.
- **Errors:**
  - `GatewayError` — Gateway failed to start listener

### stop

- **Signature:** `stop() -> None`
- **Parameters:** none
- **Returns:** None. Signals the main loop to exit after the current activation completes. Does not interrupt in-progress activations.

### trigger

- **Signature:** `trigger(task_type: str, context: dict | None = None) -> ActivationResult`
- **Parameters:**
  - task_type: str — activation type (see Activation Types table)
  - context: dict | None — optional context for the activation (e.g., `{"message": InboundMessage}` for "respond")
- **Returns:** ActivationResult
- **Errors:**
  - `UnknownTaskTypeError` — task_type not recognized
  - Module-specific errors propagated from the activated modules

Manual trigger for programmatic or debugging use. Bypasses schedule gates but respects the consolidation lock for distillation.

## Activation Types

| Type | Modules Involved | Default Trigger | Lateral Budget |
|------|-----------------|-----------------|----------------|
| `ingestion` | Source Ingestion → Attention Filter → Memory Store | Scheduled (e.g., every 4h) | Yes |
| `distillation_t1t2` | Distillation Engine (T1→T2) | Threshold via `check_gates` | No |
| `distillation_t2t3` | Distillation Engine (T2→T3) | Monthly via `check_gates` | No |
| `generation` | Generator → Output Router → Gateway | Scheduled (e.g., daily) | Yes |
| `free_play` | Generator → Output Router → Gateway | Tension threshold or scheduled | Full budget |
| `respond` | Generator → Output Router → Gateway | Inbound message from Gateway | No |
| `explore` | Explorer → Attention Filter → Memory Store | Triggered by linked_urls in accepted fragments | Yes |
| `decay` | Memory Store (`run_decay`) | Scheduled (e.g., daily) | No |

## Activation Lifecycle

Every activation follows this sequence:

```
1. Trigger           cron / tension threshold / inbound message / manual
        ↓
2. Assemble context  AmbientContext built from system state + custom streams
        ↓
3. Budget check      compute activation budget (base × tension multiplier × quiet-day ratio)
        ↓
4. Execute task      dispatch to appropriate module(s) per activation type
        ↓
5. Lateral check     if lateral budget remains AND unresolved tension > threshold:
                       Generator gets a free-play turn with remaining budget
        ↓
6. Route outputs     GeneratorOutput → Output Router → Gateway → platforms
        ↓
7. Collect feedback  Gateway feedback signals → Feedback Collector → Memory Store
        ↓
8. Log               ActivationResult logged with ambient context snapshot
```

### Step 2: Ambient Context Assembly

AmbientContext is assembled fresh at the start of every activation. It is available to all modules during the activation but is not stored in Memory Store — it is environmental context, not content.

Sources:
- **Temporal**: current timestamp, day of week, time of day
- **Budget**: remaining token budget (today), trend (computed from recent days)
- **Interaction**: activation count today, time since last human interaction (from Gateway)
- **Memory**: `memory_store.get_density_metrics()` — note count, mean link degree, unresolved count
- **Custom**: any registered `AmbientStreamDef` callables (e.g., weather API, external feeds)

### Step 5: Lateral Freedom

When the scheduled task completes and lateral budget remains:

1. Query `memory_store.get_density_metrics()` for current `max_unresolvedness`.
2. If `max_unresolvedness > config.tension_threshold`: the Generator receives the remaining lateral budget and the full affordance list.
3. The Generator's lateral output is tagged `is_lateral=True` and `output_mode="lateral"`.
4. Lateral outputs are routed through Output Router and Gateway like any other output.
5. Lateral movement is weighted toward threads with high `unresolvedness × link_count` — material the system keeps encountering from multiple angles without resolving.

The lateral budget is a fraction of the activation's total token budget (`config.lateral_budget_ratio`, default 15%). It is not rolled over between activations.

### Tension-Responsive Scheduling

The Orchestrator periodically checks unresolved tension via `memory_store.get_density_metrics()`:

- **High tension** (`max_unresolvedness > tension_threshold`): increases activation frequency (shortens cron intervals), allocates `high_tension_budget_multiplier` to budgets, and may trigger a dedicated `free_play` activation.
- **Low tension** (`max_unresolvedness < tension_threshold * 0.5`): runs at reduced budget (`quiet_day_budget_ratio`), banks the remainder for future high-tension periods.
- **Distillation triggers**: after each `ingestion` activation, checks `distillation_engine.check_gates()` and runs distillation if ready.

### Distillation Integration

After `distill_t2_to_t3` returns an `EvolutionResult`:

1. `criteria_adjustments` are applied to the Attention Filter's config for subsequent filter runs.
2. Supersession records are logged for personality development tracking.
3. If any personality file was superseded, the next `generation` activation uses the updated context (via `memory_store.get_personality_context()` which always loads fresh).

## Inputs

- **OrchestratorConfig** — schedule, budgets, thresholds, ambient stream definitions. Provided at construction, can be reloaded at runtime.
- **ModuleRefs** — references to all Phosphene modules. Provided at construction.
- **Inbound messages** — from Gateway, triggering `respond` activations.
- **Cron triggers** — from the system clock, triggering scheduled activations.
- **Manual triggers** — via `trigger()` for programmatic or debugging use.

## Outputs

- **ActivationResult** — per-activation: what ran, what was produced, whether lateral movement occurred, budget consumed.
- **GeneratorOutput** — routed to platforms via Output Router → Gateway. All outputs carry `intent_tag` and `output_mode` for feedback interpretation.
- **Logs** — each activation is logged with its AmbientContext snapshot and ActivationResult for monitoring and debugging.

## State

- **Schedule state**: active cron entries, next-fire times. In-memory, derived from config.
- **Budget tracking**: tokens used today, banked budget from quiet days. Persisted to a metadata file in the Memory Store vault (alongside distillation timestamps).
- **Interaction tracker**: timestamp of last human interaction (from Gateway). In-memory, reset on restart.
- **Running flag**: whether the main loop is active. In-memory.

The Orchestrator does not own any content state — all content lives in Memory Store. Budget and schedule metadata are lightweight operational state.

## Usage Example

```python
from orchestrator import Orchestrator, OrchestratorConfig, ScheduleEntry, ModuleRefs, AmbientStreamDef
from memory_store import MemoryStore, MemoryStoreConfig
from attention_filter import AttentionFilter, AttentionFilterConfig, FilterCriterion
from distillation import DistillationEngine, DistillationConfig
from llm_client import LLMConfig, ModelTier
from embedding import EmbeddingConfig

# Initialize all modules
store = MemoryStore(MemoryStoreConfig(vault_path="./memory", embedding_path="./memory/embeddings"))
af = AttentionFilter(memory_store=store)
distill = DistillationEngine(memory_store=store)
# ... initialize remaining modules (source_ingestion, generator, output_router, gateway, feedback, explorer)

modules = ModuleRefs(
    memory_store=store,
    attention_filter=af,
    distillation_engine=distill,
    source_ingestion=source_ingestion,
    generator=generator,
    output_router=output_router,
    gateway=gateway,
    feedback_collector=feedback,
    explorer=explorer,
)

config = OrchestratorConfig(
    schedule=[
        ScheduleEntry("ingestion", "0 */4 * * *"),          # every 4 hours
        ScheduleEntry("generation", "0 10 * * *"),           # daily at 10am
        ScheduleEntry("decay", "0 3 * * *"),                 # daily at 3am
    ],
    lateral_budget_ratio=0.15,
    tension_threshold=0.7,
    base_activation_budget=8000,
    ambient_streams=[
        AmbientStreamDef("time_context", lambda: {"season": "spring", "moon_phase": "waning"},
                         "Temporal and environmental context"),
    ],
)

# Start the system
orchestrator = Orchestrator(modules, config)
orchestrator.start()  # blocks — runs until stop() or SIGTERM

# Or trigger a single activation manually (for testing)
result = orchestrator.trigger("ingestion")
print(f"Ingestion: {len(result.outputs)} outputs, lateral={result.lateral_movement}")
print(f"Budget: {result.budget_used} tokens ({result.lateral_budget_used} lateral)")
```

### Minimal Deployment

```python
# Systemd service entry point
import signal

orchestrator = Orchestrator(modules, config)
signal.signal(signal.SIGTERM, lambda *_: orchestrator.stop())
orchestrator.start()
```
