"""Sidecar embedding persistence for Memory Store notes."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy import ndarray


def save_embedding(embedding_path: Path, note_id: str, embedding: ndarray) -> None:
    """Store an embedding vector as ``<embedding_path>/<note_id>.npy``."""
    embedding_path.mkdir(parents=True, exist_ok=True)
    np.save(embedding_path / f"{note_id}.npy", embedding)


def load_embedding(embedding_path: Path, note_id: str) -> ndarray | None:
    """Load a stored embedding vector, or return None if none exists."""
    path = embedding_path / f"{note_id}.npy"
    if not path.exists():
        return None
    return np.load(path)


def delete_embedding(embedding_path: Path | None, note_id: str) -> None:
    """Remove a stored embedding vector if one exists."""
    if embedding_path is None:
        return

    path = embedding_path / f"{note_id}.npy"
    if path.exists():
        path.unlink()
