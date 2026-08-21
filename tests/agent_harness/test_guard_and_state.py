from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

guard = importlib.import_module("agent_harness.guard")
state = importlib.import_module("agent_harness.state")


@pytest.mark.parametrize(
    ("command", "permission"),
    [
        ("python -m pytest -q", "allow"),
        ("git push --force origin main", "deny"),
        ("git reset --hard HEAD", "deny"),
        ("rm -rf /tmp/x", "deny"),
        ("Remove-Item -Recurse -Force .\\tmp", "deny"),
        ("DROP TABLE users", "deny"),
        ("Remove-Item data/reference/real/SALIDA_DGS.xlsx", "deny"),
        ("git push origin HEAD", "ask"),
        ("git commit -m 'x'", "ask"),
        ("Get-ChildItem data/reference/real", "allow"),
    ],
)
def test_classify_shell_command(command: str, permission: str) -> None:
    assert guard.classify_shell_command(command).permission == permission


def test_pending_verify_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(state, "HARNESS_STATE_DIR", tmp_path / "harness")
    monkeypatch.setattr(state, "PENDING_VERIFY_FILE", tmp_path / "harness" / "pending_verify")
    monkeypatch.setattr(state, "LAST_VERDICT_FILE", tmp_path / "harness" / "last_verdict.json")

    assert state.is_pending_verify() is False
    state.mark_pending_verify("edit:foo.py")
    assert state.is_pending_verify() is True
    assert state.pending_reason() == "edit:foo.py"
    state.clear_pending_verify()
    assert state.is_pending_verify() is False


def test_progress_open_items(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    progress = tmp_path / "progress.json"
    progress.write_text(
        '{"items":[{"id":"1","title":"a","passes":false},{"id":"2","title":"b","passes":true}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(state, "PROGRESS_FILE", progress)
    assert state.progress_has_open_items() is True
    progress.write_text(
        '{"items":[{"id":"1","title":"a","passes":true}]}',
        encoding="utf-8",
    )
    assert state.progress_has_open_items() is False
