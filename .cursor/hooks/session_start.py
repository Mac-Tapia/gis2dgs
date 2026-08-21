#!/usr/bin/env python
"""sessionStart: inject harness context for GIS2DGS agents."""

from __future__ import annotations

import json
import sys
from pathlib import Path

CONTEXT = """
GIS2DGS agent harness is active.
- Read skills/gis2dgs/SKILL.md before code changes.
- Always / Ask / Never tiers live in AGENTS.md.
- After changing src/, tests/, scripts/, or config/, run:
  python scripts/run_verify_gate.py
- Do not invent brand-specific converters; use schema + YAML adapters.
- Write outputs under output/; never overwrite data/reference/real/.
""".strip()


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()


def main() -> int:
    try:
        _ = sys.stdin.read()
        hooks_dir = Path(__file__).resolve().parent
        root = hooks_dir.parents[2]
        scripts = str(root / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)

        from agent_harness.state import is_pending_verify, progress_has_open_items

        notes = [CONTEXT]
        if is_pending_verify():
            notes.append(
                "Pending verification gate is SET — clear it with verify_gate before claiming done."
            )
        if progress_has_open_items():
            notes.append(
                "agent/progress.json has open items (passes=false). Continue until all pass."
            )
        _emit({"additional_context": "\n".join(notes)})
        return 0
    except Exception as exc:  # noqa: BLE001
        _emit({"additional_context": f"{CONTEXT}\n(harness session_start degraded: {exc})"})
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
