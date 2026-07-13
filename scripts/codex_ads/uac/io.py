"""YAML and JSON persistence for the deterministic UAC helper."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .types import ContractError

yaml: Any
try:
    import yaml as yaml
except ImportError:  # pragma: no cover - exercised by CLI error path
    yaml = None


def _load(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        value = json.loads(text)
    else:
        if yaml is None:
            raise ContractError(
                "PyYAML is required for YAML input; use JSON or install PyYAML"
            )
        try:
            value = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ContractError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{path} must contain an object at the top level")
    return value


def _dump(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        text = json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n"
    else:
        if yaml is None:
            raise ContractError("PyYAML is required for YAML output")
        text = yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = temporary.name
        os.replace(temporary_path, path)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)
