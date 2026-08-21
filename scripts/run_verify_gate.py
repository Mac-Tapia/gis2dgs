#!/usr/bin/env python
"""CLI entry for the agent harness verification gate."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from agent_harness.verify_gate import main

if __name__ == "__main__":
    raise SystemExit(main())
