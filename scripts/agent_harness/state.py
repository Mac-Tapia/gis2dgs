from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import (
    HARNESS_STATE_DIR,
    LAST_VERDICT_FILE,
    PENDING_VERIFY_FILE,
    PROGRESS_FILE,
)


def harness_dir() -> Path:
    HARNESS_STATE_DIR.mkdir(parents=True, exist_ok=True)
    return HARNESS_STATE_DIR


def mark_pending_verify(reason: str = "code_edit") -> None:
    harness_dir()
    PENDING_VERIFY_FILE.write_text(reason.strip() or "code_edit", encoding="utf-8")


def clear_pending_verify() -> None:
    if PENDING_VERIFY_FILE.exists():
        PENDING_VERIFY_FILE.unlink()


def is_pending_verify() -> bool:
    return PENDING_VERIFY_FILE.exists()


def pending_reason() -> str:
    if not PENDING_VERIFY_FILE.exists():
        return ""
    return PENDING_VERIFY_FILE.read_text(encoding="utf-8").strip()


def write_verdict(payload: dict[str, Any]) -> Path:
    harness_dir()
    LAST_VERDICT_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return LAST_VERDICT_FILE


def read_verdict() -> dict[str, Any] | None:
    if not LAST_VERDICT_FILE.exists():
        return None
    return json.loads(LAST_VERDICT_FILE.read_text(encoding="utf-8"))


def read_progress() -> dict[str, Any] | None:
    if not PROGRESS_FILE.exists():
        return None
    return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))


def progress_has_open_items() -> bool:
    data = read_progress()
    if not data:
        return False
    items = data.get("items") or []
    return any(not bool(item.get("passes")) for item in items)
