#!/usr/bin/env python
"""stop: soft/strict verification loop for unfinished harness work."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        status = str(payload.get("status") or "completed")
        loop_count = int(payload.get("loop_count") or 0)

        if status in {"aborted", "error"}:
            _emit({})
            return 0

        hooks_dir = Path(__file__).resolve().parent
        root = hooks_dir.parents[2]
        scripts = str(root / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)

        from agent_harness.state import (
            is_pending_verify,
            pending_reason,
            progress_has_open_items,
        )
        from agent_harness.verify_gate import run_verify_gate

        pending = is_pending_verify()
        open_progress = progress_has_open_items()
        if not pending and not open_progress:
            _emit({})
            return 0

        strict = os.environ.get("GIS2DGS_HARNESS_STRICT", "").strip() in {
            "1",
            "true",
            "TRUE",
            "yes",
        }

        if strict and pending:
            try:
                verdict = run_verify_gate(quick=False)
            except Exception as exc:  # noqa: BLE001
                _emit(
                    {
                        "followup_message": (
                            "Harness strict verify_gate crashed. Fix the environment and re-run "
                            f"`python scripts/run_verify_gate.py --json`. Error: {exc}"
                        )
                    }
                )
                return 0
            if verdict["status"] == "PASS":
                _emit({})
                return 0
            _emit(
                {
                    "followup_message": (
                        "Harness verification FAILED. Inspect `.cursor/harness/last_verdict.json`, "
                        "fix the failures, then re-run `python scripts/run_verify_gate.py`."
                    )
                }
            )
            return 0

        if loop_count >= 2:
            _emit({})
            return 0

        reasons = []
        if pending:
            reasons.append(f"pending_verify ({pending_reason() or 'code_edit'})")
        if open_progress:
            reasons.append("agent/progress.json has items with passes=false")

        _emit(
            {
                "followup_message": (
                    "Harness gate still open: "
                    + "; ".join(reasons)
                    + ". Run `python scripts/run_verify_gate.py` "
                    "(or `--quick` while iterating), update `agent/progress.json` so every item has "
                    "`passes: true`, then continue only if the gate is green."
                )
            }
        )
        return 0
    except Exception:  # noqa: BLE001
        _emit({})
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
