"""Cryptographic fingerprinting and atomic filesystem persistence."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any


def compute_sha256(path: str | Path) -> str:
    """Computes SHA-256 hex digest for a file using streaming 64 KB chunks."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Cannot compute hash: file not found: {file_path}")

    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def atomic_write_json(target_path: str | Path, data: Any, indent: int = 2) -> None:
    """Atomically writes JSON serialized data using write-to-temp-and-rename semantics."""
    target = Path(target_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    # Create temporary file in the same directory to ensure same filesystem for atomic rename
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target.parent,
        delete=False,
        prefix=".tmp_",
        suffix=".json",
    ) as tmp_file:
        temp_path = Path(tmp_file.name)
        json.dump(data, tmp_file, indent=indent, ensure_ascii=False)
        tmp_file.flush()
        os.fsync(tmp_file.fileno())

    try:
        os.replace(temp_path, target)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def read_json(target_path: str | Path) -> Any:
    """Reads and parses a JSON file."""
    path = Path(target_path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
