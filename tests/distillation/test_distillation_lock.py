import pytest

from phosphene.distillation.engine import DistillationEngine
from phosphene.distillation.errors import DistillationLockError


class LockOnlyMemoryStore:
    def __init__(self, vault_path):
        self.vault_path = vault_path

    def query_notes(self, *_args: object, **_kwargs: object) -> list[object]:
        raise AssertionError("lock helper must not query notes")

    def store_note(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("lock helper must not store notes")

    def update_note(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("lock helper must not update notes")

    def add_links(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("lock helper must not add links")

    def get_personality_context(self) -> object:
        raise AssertionError("lock helper must not load personality context")

    def supersede(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("lock helper must not supersede notes")


def test_consolidation_lock_acquires_and_releases_deterministically(tmp_path) -> None:
    engine = DistillationEngine(LockOnlyMemoryStore(tmp_path / "vault"))

    assert engine._is_consolidation_locked() is False

    with engine._acquire_consolidation_lock():
        assert engine._is_consolidation_locked() is True

    assert engine._is_consolidation_locked() is False


def test_consolidation_lock_rejects_nested_acquire(tmp_path) -> None:
    engine = DistillationEngine(LockOnlyMemoryStore(tmp_path / "vault"))

    with engine._acquire_consolidation_lock():
        with pytest.raises(DistillationLockError, match="another distillation run is already active"):
            with engine._acquire_consolidation_lock():
                pass

    assert engine._is_consolidation_locked() is False


def test_consolidation_lock_releases_after_exception(tmp_path) -> None:
    engine = DistillationEngine(LockOnlyMemoryStore(tmp_path / "vault"))

    with pytest.raises(RuntimeError, match="boom"):
        with engine._acquire_consolidation_lock():
            raise RuntimeError("boom")

    assert engine._is_consolidation_locked() is False
    with engine._acquire_consolidation_lock():
        assert engine._is_consolidation_locked() is True
