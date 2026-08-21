#!/usr/bin/env python
"""beforeShellExecution: deny/ask on dangerous commands."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        command = str(
            payload.get("command")
            or (payload.get("tool_input") or {}).get("command")
            or ""
        )

        hooks_dir = Path(__file__).resolve().parent
        root = hooks_dir.parents[2]
        scripts = str(root / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)

        from agent_harness.guard import classify_shell_command

        decision = classify_shell_command(command)
        out = {
            "permission": decision.permission,
            "user_message": decision.reason if decision.permission != "allow" else "",
            "agent_message": decision.reason if decision.permission != "allow" else "",
        }
        _emit(out)
        return 0
    except Exception as exc:  # noqa: BLE001
        # Fail open with an explicit note so the agent is not locked out of the repo.
        _emit(
            {
                "permission": "allow",
                "agent_message": f"harness guard_shell degraded: {exc}",
            }
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
