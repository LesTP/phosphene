import pytest

from phosphene.memory_store import (
    AlreadySupersededError,
    DimensionMismatchError,
    InvalidScoreError,
    InvalidTierError,
    MemoryStoreError,
    NoteNotFoundError,
    TierMismatchError,
    TitleTooLongError,
    VaultError,
)


ERROR_TYPES = [
    VaultError,
    InvalidTierError,
    TitleTooLongError,
    InvalidScoreError,
    NoteNotFoundError,
    DimensionMismatchError,
    TierMismatchError,
    AlreadySupersededError,
]


def test_errors_inherit_from_memory_store_error() -> None:
    for error_type in ERROR_TYPES:
        assert issubclass(error_type, MemoryStoreError)


def test_errors_construct_and_catch_via_base_class() -> None:
    for error_type in ERROR_TYPES:
        with pytest.raises(MemoryStoreError) as exc_info:
            raise error_type("message")

        assert isinstance(exc_info.value, error_type)
        assert str(exc_info.value) == "message"
