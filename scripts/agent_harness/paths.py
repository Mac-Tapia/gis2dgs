from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS_STATE_DIR = ROOT / ".cursor" / "harness"
PENDING_VERIFY_FILE = HARNESS_STATE_DIR / "pending_verify"
LAST_VERDICT_FILE = HARNESS_STATE_DIR / "last_verdict.json"
PROGRESS_FILE = ROOT / "agent" / "progress.json"
