from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

verify_gate = importlib.import_module("agent_harness.verify_gate")
state = importlib.import_module("agent_harness.state")


def test_run_verify_gate_quick(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(state, "HARNESS_STATE_DIR", tmp_path / "harness")
    monkeypatch.setattr(state, "PENDING_VERIFY_FILE", tmp_path / "harness" / "pending_verify")
    monkeypatch.setattr(state, "LAST_VERDICT_FILE", tmp_path / "harness" / "last_verdict.json")
    monkeypatch.setattr(verify_gate, "write_verdict", state.write_verdict)
    monkeypatch.setattr(verify_gate, "clear_pending_verify", state.clear_pending_verify)

    state.mark_pending_verify("test")
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], timeout: int) -> dict:
        calls.append(cmd)
        return {
            "cmd": cmd,
            "returncode": 0,
            "elapsed_s": 0.01,
            "stdout_tail": "ok",
            "stderr_tail": "",
            "pass": True,
        }

    monkeypatch.setattr(verify_gate, "_run", fake_run)
    verdict = verify_gate.run_verify_gate(quick=True)
    assert verdict["status"] == "PASS"
    assert len(calls) == 2
    assert state.is_pending_verify() is False
    saved = json.loads((tmp_path / "harness" / "last_verdict.json").read_text(encoding="utf-8"))
    assert saved["status"] == "PASS"
