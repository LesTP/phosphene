"""Phase 1 smoke test: construct each migrated toolkit module with stubs."""

import sys
import tempfile
from datetime import datetime, timezone
from dataclasses import dataclass

sys.path.insert(0, "src")
sys.path.insert(0, "../toolkit/src")

# 1. Gateway with telegram adapter (exercises toolkit.gateway → toolkit.telegram_client wire)
from toolkit.gateway import (
    Gateway, GatewayConfig, PlatformConfig, FeedbackSignal, DeliveryResult,
)

gw = Gateway(
    GatewayConfig(
        platforms=[
            PlatformConfig(
                name="telegram",
                adapter_type="telegram",
                credentials={"bot_token": "123456:ABC-DEF-fake"},
                params={"chat_id": "42"},
                output_formats=["text", "markdown", "telegraph"],
            ),
            PlatformConfig(
                name="log",
                adapter_type="log",
                credentials={},
                params={"log_path": tempfile.mktemp(suffix=".jsonl")},
            ),
        ],
        default_platform="telegram",
        listen=False,
    ),
    on_message=lambda m: None,
    on_feedback=lambda s: None,
)
platforms = list(gw._adapters_by_platform.keys())
tg_adapter = gw._adapters_by_platform["telegram"]
print(f"Gateway: platforms={platforms}")
print(f"  telegram adapter: {type(tg_adapter).__module__}.{type(tg_adapter).__name__}")

# 2. SourceIngestion (exercises toolkit.source_ingestion wire)
from toolkit.source_ingestion import SourceIngestion, IngestionConfig, AdapterConfig

si = SourceIngestion(IngestionConfig(adapters=[
    AdapterConfig(
        adapter_type="corpus_text",
        source_label="test",
        params={
            "archive_path": tempfile.gettempdir(),
            "marker_store_path": tempfile.mktemp(suffix=".json"),
        },
    ),
]))
print(f"SourceIngestion: {len(si.config.adapters)} adapter configured")

# 3. FeedbackCollector with duck-typed fake memory store (exercises D-4 contract)
from toolkit.feedback_collector import FeedbackCollector

class FakeMemoryStore:
    def get_note(self, note_id):
        class N:
            tags = ["friction"]
            tier = 1
            unresolvedness = 0.5
        return N()

    def store_note(self, note):
        for attr in ("tier", "content", "title", "importance", "tags"):
            assert hasattr(note, attr), f"_NoteInput missing {attr}"
        return "fake-id"

    def update_note(self, note_id, patch):
        assert hasattr(patch, "unresolvedness"), "_NotePatch missing unresolvedness"
        return None

fc = FeedbackCollector(memory_store=FakeMemoryStore())
print(f"FeedbackCollector: memory_store={type(fc.memory_store).__name__}")

@dataclass
class FakeOutput:
    intent_tag: str = "synthesis"
    output_mode: str = "prompted"
    source_note_ids: list = None
    def __post_init__(self):
        if self.source_note_ids is None:
            self.source_note_ids = ["n1", "n2"]

fc.register_output(
    FakeOutput(),
    DeliveryResult(success=True, platform="telegram", message_id="msg-1"),
)
sig = FeedbackSignal(
    platform="telegram", message_id="msg-1", signal_type="reaction",
    value="👍", sender="42", timestamp=datetime.now(timezone.utc),
)
event = fc.process_signal(sig)
assert event is not None, "process_signal returned None"
print(f"  process_signal -> signal_type={event.signal_type}, "
      f"source_notes={event.source_note_ids}")

print()
print("SMOKE TEST PASSED: all three migrated modules construct + wire correctly")
