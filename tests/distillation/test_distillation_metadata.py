from datetime import datetime, timezone
import json

from phosphene.distillation.engine import DistillationEngine, _DistillationRunMetadata


class MetadataOnlyMemoryStore:
    def __init__(self, vault_path):
        self.vault_path = vault_path

    def query_notes(self, *_args: object, **_kwargs: object) -> list[object]:
        raise AssertionError("metadata helpers must not query notes")

    def store_note(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("metadata helpers must not store notes")

    def update_note(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("metadata helpers must not update notes")

    def add_links(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("metadata helpers must not add links")

    def get_personality_context(self) -> object:
        raise AssertionError("metadata helpers must not load personality context")

    def supersede(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("metadata helpers must not supersede notes")


def test_run_metadata_missing_file_returns_never_run(tmp_path) -> None:
    engine = DistillationEngine(MetadataOnlyMemoryStore(tmp_path / "vault"))

    metadata = engine._read_run_metadata()

    assert metadata.last_t1_to_t2_run is None
    assert metadata.last_t2_to_t3_run is None


def test_run_metadata_round_trips_timestamps_in_vault_metadata_file(tmp_path) -> None:
    engine = DistillationEngine(MetadataOnlyMemoryStore(tmp_path / "vault"))
    t1_run = datetime(2026, 5, 1, 8, 30, 5, tzinfo=timezone.utc)
    t3_run = datetime(2026, 5, 2, 9, 45, 6, tzinfo=timezone.utc)

    engine._write_run_metadata(
        _DistillationRunMetadata(
            last_t1_to_t2_run=t1_run,
            last_t2_to_t3_run=t3_run,
        )
    )

    assert engine._run_metadata_path == tmp_path / "vault" / ".phosphene" / "distillation_runs.json"
    payload = json.loads(engine._run_metadata_path.read_text(encoding="utf-8"))
    assert payload == {
        "last_t1_to_t2_run": "2026-05-01T08:30:05+00:00",
        "last_t2_to_t3_run": "2026-05-02T09:45:06+00:00",
    }
    assert engine._read_run_metadata() == _DistillationRunMetadata(
        last_t1_to_t2_run=t1_run,
        last_t2_to_t3_run=t3_run,
    )


def test_run_metadata_malformed_file_is_treated_as_never_run(tmp_path) -> None:
    engine = DistillationEngine(MetadataOnlyMemoryStore(tmp_path / "vault"))
    engine._run_metadata_path.parent.mkdir(parents=True)
    engine._run_metadata_path.write_text("{not-json", encoding="utf-8")

    metadata = engine._read_run_metadata()

    assert metadata == _DistillationRunMetadata()


def test_run_metadata_ignores_malformed_fields_independently(tmp_path) -> None:
    engine = DistillationEngine(MetadataOnlyMemoryStore(tmp_path / "vault"))
    engine._run_metadata_path.parent.mkdir(parents=True)
    engine._run_metadata_path.write_text(
        json.dumps(
            {
                "last_t1_to_t2_run": "not-a-timestamp",
                "last_t2_to_t3_run": "2026-05-02T09:45:06+00:00",
            }
        ),
        encoding="utf-8",
    )

    metadata = engine._read_run_metadata()

    assert metadata == _DistillationRunMetadata(
        last_t1_to_t2_run=None,
        last_t2_to_t3_run=datetime(2026, 5, 2, 9, 45, 6, tzinfo=timezone.utc),
    )
