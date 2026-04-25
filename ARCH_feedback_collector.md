# ARCH: Feedback Collector

## Purpose
Normalizes feedback signals from the Gateway (reactions, replies, silence) into structured feedback events stored in Memory Store. Closes the loop between output and personality development — the Distillation engine reads these events to calibrate Attention Filter criteria weights and inform personality file evolution. Does not directly modify any module's behavior in real time; all feedback influence is mediated through the distillation cycle.

## Public API

### Types

```python
@dataclass
class FeedbackEvent:
    output_message_id: str                          # Gateway message_id of the output that received feedback
    output_intent_tag: str                          # intent_tag from GeneratorOutput (for criteria attribution)
    output_mode: str                                # output_mode from GeneratorOutput
    signal_type: str                                # "like", "dislike", "reply", "forward", "silence"
    signal_value: str | None = None                 # reaction emoji, reply text, etc.
    source_note_ids: list[str] = field(default_factory=list)
                                                    # note_ids that contributed to the output (from GeneratorOutput)
    retention_criteria: list[str] = field(default_factory=list)
                                                    # criteria tags from the original Tier 1 notes that fed this output
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class FeedbackCollectorConfig:
    silence_window: timedelta = timedelta(hours=24) # how long to wait before recording silence as signal
    positive_reactions: list[str] = field(default_factory=lambda: ["👍", "❤️", "🔥", "💡", "🤔"])
    negative_reactions: list[str] = field(default_factory=lambda: ["👎"])
    reply_is_positive: bool = True                  # treat any reply as positive engagement (human took time to respond)
    forward_is_positive: bool = True                # treat forwards as strong positive signal

@dataclass
class OutputRecord:
    message_id: str                                 # Gateway-assigned message_id
    intent_tag: str                                 # from GeneratorOutput
    output_mode: str                                # from GeneratorOutput
    source_note_ids: list[str]                      # from GeneratorOutput
    retention_criteria: list[str]                    # aggregated criteria from the source Tier 1 notes
    delivered_at: datetime
    feedback_events: list[FeedbackEvent] = field(default_factory=list)
    silence_recorded: bool = False                  # whether silence has been recorded for this output
```

### Constructor

- **Signature:** `FeedbackCollector(memory_store: MemoryStore, config: FeedbackCollectorConfig | None = None)`
- **Parameters:**
  - memory_store: MemoryStore — for storing feedback events and looking up source notes
  - config: FeedbackCollectorConfig | None — defaults used if None
- **Errors:** none

### register_output

- **Signature:** `register_output(output: GeneratorOutput, delivery: DeliveryResult) -> None`
- **Parameters:**
  - output: GeneratorOutput — the generated content (for intent_tag, source_note_ids)
  - delivery: DeliveryResult — from Gateway (for message_id, platform)
- **Returns:** None. Records the output for feedback tracking.
- **Errors:** none (silently ignores outputs with no message_id, e.g., failed deliveries)

**Called by the Orchestrator after each successful Gateway delivery.** Creates an `OutputRecord` that maps the message_id to the output metadata needed for feedback attribution.

### process_signal

- **Signature:** `process_signal(signal: FeedbackSignal) -> FeedbackEvent | None`
- **Parameters:**
  - signal: FeedbackSignal — from Gateway (reaction, reply, forward)
- **Returns:** FeedbackEvent if the signal maps to a registered output, None if the message_id is unknown (stale or untracked)
- **Errors:** none

**Behavior:**
1. Looks up the `OutputRecord` for `signal.message_id`.
2. Classifies the signal:
   - Reaction in `positive_reactions` → `signal_type="like"`
   - Reaction in `negative_reactions` → `signal_type="dislike"`
   - Reply → `signal_type="reply"` (positive if `reply_is_positive`)
   - Forward → `signal_type="forward"` (positive if `forward_is_positive`)
   - Unknown reaction → ignored
3. Builds a `FeedbackEvent` with the output's `intent_tag`, `source_note_ids`, and `retention_criteria`.
4. Stores the event in Memory Store as a Tier 1 note with `source="feedback"`.
5. Returns the event.

### check_silence

- **Signature:** `check_silence() -> list[FeedbackEvent]`
- **Parameters:** none
- **Returns:** list[FeedbackEvent] — silence events for outputs that received no feedback within `silence_window`
- **Errors:** none

**Called periodically by the Orchestrator (e.g., during decay activation).** For each `OutputRecord` where `delivered_at + silence_window` has passed and no feedback was received, records a `signal_type="silence"` event. Silence is a meaningful signal — content the human ignored is data about what doesn't land.

## How Feedback Flows to Distillation

Feedback events are stored as Tier 1 notes with `source="feedback"`:

```python
memory_store.store_note(NoteInput(
    tier=1,
    content=f"Feedback: {event.signal_type} on [{event.output_intent_tag}] output",
    title=f"Feedback: {event.signal_type} on {event.output_intent_tag}",
    importance=importance_from_signal(event.signal_type),
    tags=["feedback", event.signal_type, event.output_intent_tag] + event.retention_criteria,
    source="feedback",
    links=event.source_note_ids,
))
```

The Distillation engine reads these during `distill_t1_to_t2` (when `incorporate_feedback=True`):
- Notes linked to well-received outputs get importance boosts
- `retention_criteria` tags on feedback events allow per-criterion engagement tracking
- The `criteria_adjustments` output from `distill_t2_to_t3` reflects which criteria consistently produce liked vs. ignored content

**Importance mapping:**

| Signal | Importance | Rationale |
|--------|-----------|-----------|
| `forward` | 0.9 | Strongest positive — human shared it further |
| `like` (💡🤔) | 0.7 | Engaged, intellectually |
| `like` (👍❤️🔥) | 0.6 | Engaged, general approval |
| `reply` | 0.7 | Human took time to respond |
| `dislike` | 0.8 | High importance — negative signal is strong data |
| `silence` | 0.3 | Weak negative — content didn't land, but absence is ambiguous |

## Inputs

- **FeedbackSignal** — from Gateway via `on_feedback` callback. Reactions, replies, forwards on delivered messages.
- **GeneratorOutput + DeliveryResult** — from Orchestrator via `register_output`. Maps message_ids to output metadata.
- **FeedbackCollectorConfig** — signal classification rules, silence window.

## Outputs

- **FeedbackEvent** — stored in Memory Store as Tier 1 notes with `source="feedback"`. Consumed by the Distillation engine.
- **Silence events** — generated by `check_silence`. Same storage path.

## State

- **Output records:** in-memory map of `message_id → OutputRecord`. Bounded — records older than `2 × silence_window` are evicted (feedback on very old messages is unlikely and not useful for calibration). Not persisted — lost on restart, which is acceptable since silence detection resets.
- No other state. All durable feedback data lives in Memory Store.

## Usage Example

```python
from feedback_collector import FeedbackCollector, FeedbackCollectorConfig
from memory_store import MemoryStore

store = MemoryStore(MemoryStoreConfig(vault_path="./memory"))
fc = FeedbackCollector(memory_store=store, config=FeedbackCollectorConfig(
    silence_window=timedelta(hours=24),
    positive_reactions=["👍", "❤️", "🔥", "💡", "🤔"],
))

# Orchestrator registers each delivered output
fc.register_output(generator_output, delivery_result)

# Gateway feedback callback (wired by Orchestrator)
def on_feedback(signal: FeedbackSignal):
    event = fc.process_signal(signal)
    if event:
        print(f"Feedback: {event.signal_type} on {event.output_intent_tag}")

# Periodic silence check (during decay activation)
silence_events = fc.check_silence()
for event in silence_events:
    print(f"Silence on {event.output_intent_tag} output from {event.timestamp}")
```
