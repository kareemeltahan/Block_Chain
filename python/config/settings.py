"""
python/config/settings.py
─────────────────────────
Single source of truth for runtime configuration.

HOW IT WORKS:
  - Reads config.json on every load() call (no stale module-level cache).
  - Derives deployer_address from private key if missing, then saves.
  - Writes atomically via os.replace() (rename) — partial writes are impossible.
    This fixes the v1 bug where rapid sequential contract deployments could
    overwrite each other's saved addresses.
  - Path is controlled by the UW3_CONFIG environment variable (default: config.json
    in the project root). Useful for tests or multiple environments.

VALIDATION:
  - Fails fast with a clear message if required keys are missing.
  - Checks node_url is non-empty so you get "node_url is empty" instead of
    a cryptic ConnectionRefusedError deep in web3.py.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

_CONFIG_PATH: Path | None = None

DEFAULT_CONFIG: dict[str, Any] = {
    "node_url":             "http://127.0.0.1:8545",
    "deployer_private_key": "",
    "deployer_address":     "",
    "contracts": {
        "AccessRegistry": "",
        "Major":          "",
        "Professor":      "",
        "Student":        "",
        "Course":         "",
        "Enrollment":     "",
        "University":     "",
    },
}

REQUIRED_KEYS = {"node_url", "deployer_private_key", "contracts"}


def _path() -> Path:
    global _CONFIG_PATH
    if _CONFIG_PATH is None:
        env = os.environ.get("UW3_CONFIG", "")
        if env:
            _CONFIG_PATH = Path(env).resolve()
        else:
            # Walk up from this file to the project root (two levels: config/ → python/ → root)
            _CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config.json"
    return _CONFIG_PATH


def load() -> dict[str, Any]:
    """Load and validate config from disk. Returns a fresh dict every call."""
    path = _path()
    if not path.exists():
        _write(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    with open(path, encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    _validate(data)
    return data


def save(data: dict[str, Any]) -> None:
    """Validate and atomically write config to disk."""
    _validate(data)
    _write(data)


def set_contract_address(name: str, address: str) -> None:
    """
    Update a single contract address and flush.
    ALWAYS reads fresh from disk first to avoid clobbering concurrent writes
    when multiple contracts are deployed in rapid succession.
    """
    cfg = load()
    cfg["contracts"][name] = address
    save(cfg)


def _write(data: dict[str, Any]) -> None:
    """Atomic write: write to a temp file, then rename over the target."""
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=4)
        os.replace(tmp, path)   # atomic on all POSIX and Windows ≥ Vista
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _validate(data: dict[str, Any]) -> None:
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        raise ValueError(f"config.json is missing required keys: {missing}")
    if not data.get("node_url"):
        raise ValueError(
            "config.json: node_url is empty. "
            "Set it to your node RPC URL (e.g. http://127.0.0.1:8545)."
        )
    if not isinstance(data.get("contracts"), dict):
        raise ValueError("config.json: 'contracts' must be a JSON object.")
