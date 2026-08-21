from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any

from .paths import ROOT
from .state import clear_pending_verify, write_verdict


def _python() -> str:
    venv = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv.exists():
        return str(venv)
    return sys.executable


def _run(cmd: list[str], timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    elapsed = time.perf_counter() - started
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "elapsed_s": round(elapsed, 3),
        "stdout_tail": (proc.stdout or "")[-4000:],
        "stderr_tail": (proc.stderr or "")[-4000:],
        "pass": proc.returncode == 0,
    }


def run_verify_gate(
    *,
    quick: bool = False,
    timeout_tests: int = 600,
    timeout_integral: int = 120,
) -> dict[str, Any]:
    """Deterministic verification sensors for the agent harness."""
    py = _python()
    steps: list[dict[str, Any]] = []

    if quick:
        steps.append(
            _run(
                [py, "-m", "compileall", "-q", "src", "tests", "scripts"],
                timeout=120,
            )
        )
        steps.append(
            _run([py, "scripts/verify_integral_project.py"], timeout=timeout_integral)
        )
    else:
        steps.append(_run([py, "-m", "pytest", "-q"], timeout=timeout_tests))
        steps.append(
            _run([py, "scripts/verify_integral_project.py"], timeout=timeout_integral)
        )

    ok = all(step["pass"] for step in steps)
    payload = {
        "status": "PASS" if ok else "FAIL",
        "quick": quick,
        "steps": steps,
        "strict_env": os.environ.get("GIS2DGS_HARNESS_STRICT", ""),
    }
    write_verdict(payload)
    if ok:
        clear_pending_verify()
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="GIS2DGS agent harness verification gate",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="compileall + verify_integral only (skip full pytest)",
    )
    parser.add_argument("--json", action="store_true", help="Print verdict JSON")
    args = parser.parse_args(argv)

    try:
        verdict = run_verify_gate(quick=args.quick)
    except subprocess.TimeoutExpired as exc:
        payload = {
            "status": "FAIL",
            "error": f"timeout: {exc}",
        }
        write_verdict(payload)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("[FAIL] verification timed out", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(verdict, indent=2))
    else:
        print(f"[HARNESS] verify_gate -> {verdict['status']}")
        for step in verdict["steps"]:
            mark = "PASS" if step["pass"] else "FAIL"
            print(f"  [{mark}] {' '.join(step['cmd'])} ({step['elapsed_s']}s)")
        if verdict["status"] != "PASS":
            for step in verdict["steps"]:
                if not step["pass"]:
                    if step["stderr_tail"]:
                        print(step["stderr_tail"], file=sys.stderr)
                    if step["stdout_tail"]:
                        print(step["stdout_tail"])

    return 0 if verdict["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
