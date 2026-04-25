# ARCH: Generator + Output Router

## Purpose
**Generator:** Produces original content from personality context. Three modes: prompted generation (scheduled), free-play generation (lateral movement), and response generation (reply to human). Loads fresh personality context per call, enriches it with relevant Tier 2 patterns, and applies skeptical memory — checking personality claims against recent experience before generating.

**Output Router:** Maps GeneratorOutput to platform and format for delivery via Gateway. Decides channel (Telegram message, Telegraph article, internal log) and format (text, markdown, thread) based on output length, intent tag, and platform capabilities.

## Public API

### Types

```python
@dataclass
class GeneratorConfig:
    llm_config: LLMConfig                          # toolkit/llm_client — for generation
    llm_configs_rotation: list[LLMConfig] | None = None  # optional: rotation for budget management
    generation_tier: ModelTier = ModelTier.QUALITY   # model tier for generation
    verification_tier: ModelTier = ModelTier.DEFAULT  # model tier for skeptical memory check
    max_output_tokens: int = 2000                   # generation token cap
    include_tier2_patterns: bool = True             # enrich personality context with relevant Tier 2
    tier2_pattern_limit: int = 10                   # max Tier 2 patterns to include
    skeptical_memory: bool = True                   # verify personality claims against recent Tier 1
    skeptical_window_days: int = 14                 # how far back to check for contradictions

@dataclass
class GenerationPrompt:
    topic: str | None = None                        # topic or seed for prompted generation. None = system chooses.
    unresolved_thread_ids: list[str] | None = None  # note_ids of unresolved threads to engage with
    budget_tokens: int = 4000                       # token budget for this generation (including context)

@dataclass
class FreePlayTrigger:
    trigger_note_ids: list[str]                     # note_ids that triggered lateral movement (high unresolvedness × link_count)
    budget_tokens: int = 2000                       # remaining lateral budget from activation
    affordances: list[str] = field(default_factory=lambda: [
        "synthesize_across_threads", "surface_contradiction", "pose_question",
        "reframe_existing_claim", "connect_unlinked_material",
    ])                                              # what the generator is allowed to attempt

@dataclass
class GeneratorOutput:
    content: str                                    # generated text
    intent_tag: str                                 # "synthesis", "provocation", "question", "aesthetic",
                                                    # "internal_note", "log_surfacing", "subscription_proposal"
    output_mode: str                                # "prompted", "free_play", "lateral", "response"
    importance_score: float                         # [0.0, 1.0] — self-assessed
    is_lateral: bool                                # True if produced by free-play or lateral movement
    source_note_ids: list[str]                      # personality/pattern note_ids that contributed
    contradictions_noted: list[Contradiction]        # personality claims that conflicted with recent experience
    token_usage: TokenUsage                         # from toolkit/llm_client

@dataclass
class Contradiction:
    personality_note_id: str                         # the Tier 3 file containing the claim
    claim_summary: str                               # what the personality file claims
    counter_evidence_ids: list[str]                   # Tier 1 note_ids that contradict it
    counter_summary: str                              # what the recent evidence shows

@dataclass
class PersonalitySnapshot:
    personality_files: list[MemoryNote]               # current Tier 3 (from get_personality_context)
    relevant_patterns: list[MemoryNote]               # selected Tier 2 patterns (by relevance to topic)
    contradictions: list[Contradiction]                # claims not supported by recent Tier 1
    ambient_context: AmbientContext                    # environmental data for this activation
```

### Constructor

- **Signature:** `Generator(memory_store: MemoryStore)`
- **Parameters:**
  - memory_store: MemoryStore — for personality context, pattern queries, and skeptical memory verification
- **Errors:** none

### generate

- **Signature:** `generate(prompt: GenerationPrompt, ambient: AmbientContext, config: GeneratorConfig) -> GeneratorOutput`
- **Parameters:**
  - prompt: GenerationPrompt — topic and/or unresolved threads to engage with. If `topic` is None, the Generator selects a topic from unresolved threads or recent high-importance patterns.
  - ambient: AmbientContext — environmental context for this activation (from Orchestrator)
  - config: GeneratorConfig — model settings, context enrichment, skeptical memory toggle
- **Returns:** GeneratorOutput with `output_mode="prompted"`
- **Errors:**
  - `LLMAPIError` — generation LLM call failed
  - `EmptyPersonalityError` — no Tier 3 personality files exist (system not seeded)

**Behavior:**
1. Builds a `PersonalitySnapshot`: loads Tier 3 via `memory_store.get_personality_context()`, queries relevant Tier 2 patterns via `memory_store.search_by_embedding()` (if `include_tier2_patterns`), runs skeptical memory check (if enabled).
2. Constructs LLM prompt with: personality snapshot, ambient context, generation topic, and any specified unresolved threads.
3. Calls toolkit/llm_client for generation.
4. Tags output with `intent_tag` (self-classified from the content) and `importance_score` (self-assessed).
5. Records which `source_note_ids` contributed and any `contradictions_noted`.

### free_play

- **Signature:** `free_play(trigger: FreePlayTrigger, ambient: AmbientContext, config: GeneratorConfig) -> GeneratorOutput`
- **Parameters:**
  - trigger: FreePlayTrigger — the unresolved threads that triggered lateral movement, remaining budget, affordance list
  - ambient: AmbientContext
  - config: GeneratorConfig
- **Returns:** GeneratorOutput with `output_mode="free_play"` and `is_lateral=True`
- **Errors:**
  - `LLMAPIError` — generation failed
  - `EmptyPersonalityError` — not seeded

**Behavior:**
1. Builds PersonalitySnapshot (same as `generate`).
2. Loads the trigger notes from Memory Store. These are the threads with high `unresolvedness × link_count` — material the system keeps encountering without resolving.
3. Constructs LLM prompt with personality snapshot, trigger notes, and the affordance list. The prompt does not prescribe what to produce — it presents the unresolved material and the affordances and lets the model choose.
4. Output may be any intent_tag. `internal_note` outputs are logged but not delivered to platforms (the Output Router handles this).

### respond

- **Signature:** `respond(message: InboundMessage, ambient: AmbientContext, config: GeneratorConfig) -> GeneratorOutput`
- **Parameters:**
  - message: InboundMessage — the human's message (from Gateway)
  - ambient: AmbientContext
  - config: GeneratorConfig
- **Returns:** GeneratorOutput with `output_mode="response"`
- **Errors:**
  - `LLMAPIError` — generation failed
  - `EmptyPersonalityError` — not seeded

**Behavior:**
1. Builds PersonalitySnapshot.
2. Queries Memory Store for notes relevant to the message content (via `search_by_embedding`).
3. Constructs LLM prompt with personality snapshot, relevant notes, the message, and ambient context.
4. Generates a response in the personality's voice.

### Skeptical Memory

When `config.skeptical_memory` is enabled, the Generator verifies personality claims before generation:

1. For each Tier 3 personality file, extracts key claims (via a lightweight LLM call at `verification_tier`).
2. Queries recent Tier 1 notes (within `skeptical_window_days`) that are relevant to those claims (via `memory_store.search_by_embedding`).
3. If recent Tier 1 evidence contradicts a personality claim, records a `Contradiction` and includes it in the generation context — the model sees both the claim and the counter-evidence, and can choose how to handle the tension.
4. Contradictions are reported in `GeneratorOutput.contradictions_noted`. The Orchestrator can feed these back to the Distillation engine to increase `unresolvedness` on the affected personality files.

This prevents the system from repeating stale self-descriptions that its own recent experience has moved past.

---

## Output Router

### Types

```python
@dataclass
class RouterConfig:
    length_thresholds: LengthThresholds = field(default_factory=LengthThresholds)
    intent_routing: dict[str, str] = field(default_factory=lambda: {
        "internal_note": "log",           # never delivered to platforms
        "log_surfacing": "log",           # internal only
        "subscription_proposal": "log",   # internal only (for now)
    })                                    # intent_tag → platform override. Unlisted intents go to default.

@dataclass
class LengthThresholds:
    short_max: int = 500                  # chars — delivered as plain message
    medium_max: int = 3000                # chars — delivered as markdown or thread
                                          # above medium_max → Telegraph (long-form)
```

### route

- **Signature:** `route(output: GeneratorOutput, router_config: RouterConfig, gateway: Gateway) -> DeliveryResult | None`
- **Parameters:**
  - output: GeneratorOutput — the generated content to deliver
  - router_config: RouterConfig — length thresholds, intent-based routing overrides
  - gateway: Gateway — for delivery
- **Returns:** DeliveryResult from Gateway, or None if the output was routed to internal log only
- **Errors:**
  - `DeliveryError` — Gateway delivery failed (included in DeliveryResult)

**Routing logic:**

1. Check `intent_routing` for the output's `intent_tag`. If mapped to `"log"`, write to local log only, return None.
2. Determine format from content length:
   - ≤ `short_max` → `"text"`
   - ≤ `medium_max` → `"markdown"`
   - \> `medium_max` → `"telegraph"`
3. If `output.output_mode == "response"`, set `reply_to` from the originating message's ID (threading).
4. Construct `OutboundMessage` and call `gateway.send()`.

## Inputs

- **PersonalityContext** — from `memory_store.get_personality_context()`. Current Tier 3 files.
- **Tier 2 patterns** — from `memory_store.search_by_embedding()` or `memory_store.query_notes(tier=2)`. Selected by relevance to generation topic.
- **Recent Tier 1 notes** — for skeptical memory verification.
- **AmbientContext** — from Orchestrator. Environmental state.
- **InboundMessage** — for `respond` mode (from Gateway via Orchestrator).
- **FreePlayTrigger** — for `free_play` mode (from Orchestrator).

## Outputs

- **GeneratorOutput** — generated content with intent tag, mode, importance, source notes, and contradictions. Passed to Output Router.
- **OutboundMessage** — from Output Router, delivered via Gateway.
- **Contradictions** — reported in GeneratorOutput. The Orchestrator can use these to increase `unresolvedness` on affected personality files, feeding the distillation cycle.

**Resolves provisional contract:** The Generator uses `memory_store.get_personality_context()` for Tier 3 files (loaded fresh per call) and enriches them with relevant Tier 2 patterns selected by embedding similarity to the generation topic. The `include_tier2_patterns` config flag controls this. When disabled, the Generator uses Tier 3 only.

## State

None. The Generator is stateless — it loads personality context fresh per call from Memory Store. No conversation history is maintained between calls (each activation is independent, consistent with Phosphene's discontinuous activation model).

The Output Router is stateless — it's a pure routing function.

## Usage Example

```python
from generator import Generator, GeneratorConfig, GenerationPrompt, FreePlayTrigger
from generator import route, RouterConfig
from gateway import Gateway
from memory_store import MemoryStore
from llm_client import LLMConfig, ModelTier

store = MemoryStore(MemoryStoreConfig(vault_path="./memory"))
gen = Generator(memory_store=store)

config = GeneratorConfig(
    llm_config=LLMConfig(provider="anthropic", api_key="sk-...",
                         models={"quality": "claude-sonnet-..."}),
    generation_tier=ModelTier.QUALITY,
    include_tier2_patterns=True,
    skeptical_memory=True,
)

# Prompted generation (scheduled)
output = gen.generate(
    prompt=GenerationPrompt(topic="network density and surprise"),
    ambient=ambient_context,
    config=config,
)
print(f"[{output.intent_tag}] {output.content[:200]}...")
if output.contradictions_noted:
    for c in output.contradictions_noted:
        print(f"  Contradiction: {c.claim_summary} vs {c.counter_summary}")

# Free-play generation (lateral movement)
output = gen.free_play(
    trigger=FreePlayTrigger(
        trigger_note_ids=["note-073", "note-091"],
        budget_tokens=1200,
    ),
    ambient=ambient_context,
    config=config,
)

# Response to human message
output = gen.respond(
    message=inbound_msg,
    ambient=ambient_context,
    config=config,
)

# Route output to platform
result = route(output, RouterConfig(), gateway)
if result:
    print(f"Delivered to {result.platform}: {result.message_id}")
```
