#!/usr/bin/env python
"""afterFileEdit: mark verification pending when product code changes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

WATCH_PREFIXES = (
    "src/",
    "tests/",
    "scripts/",
    "config/",
    "skills/",
    "AGENTS.md",
    "pyproject.toml",
    "requirements.txt",
)


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()


def _watched(path: str, root: Path) -> bool:
    normalized = path.replace("\\", "/")
    root_prefix = root.as_posix().rstrip("/") + "/"
    if normalized.startswith(root_prefix):
        normalized = normalized[len(root_prefix) :]
    return any(normalized == p or normalized.startswith(p) for p in WATCH_PREFIXES)


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        file_path = str(
            payload.get("file_path")
            or payload.get("path")
            or (payload.get("tool_input") or {}).get("path")
            or ""
        )
        hooks_dir = Path(__file__).resolve().parent
        root = hooks_dir.parents[2]
        scripts = str(root / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)

        from agent_harness.state import mark_pending_verify

        if file_path and _watched(file_path, root):
            mark_pending_verify(f"edit:{Path(file_path).name}")
        _emit({})
        return 0
    except Exception:  # noqa: BLE001
        _emit({})
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
