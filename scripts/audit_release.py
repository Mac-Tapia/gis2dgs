from __future__ import annotations

import argparse
import compileall
import importlib
import json
import os
import pkgutil
import re
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _add_src() -> None:
    for path in (ROOT, SRC):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def _project_version() -> tuple[str, str, str]:
    _add_src()
    import gis2dgs

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    settings = yaml.safe_load((ROOT / "config/settings.yaml").read_text(encoding="utf-8"))
    return (
        gis2dgs.__version__,
        pyproject["project"]["version"],
        settings["project"]["version"],
    )


def _import_modules() -> tuple[int, list[str]]:
    _add_src()
    import gis2dgs

    errors: list[str] = []
    modules = list(pkgutil.walk_packages(gis2dgs.__path__, gis2dgs.__name__ + "."))
    for module in modules:
        try:
            importlib.import_module(module.name)
        except Exception as exc:  # pragma: no cover - audit utility
            errors.append(f"{module.name}: {exc!r}")
    return len(modules), errors


def _long_lines(limit: int = 100) -> list[str]:
    violations: list[str] = []
    for base in (ROOT / "src", ROOT / "tests", ROOT / "scripts"):
        for path in base.rglob("*.py"):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if len(line) > limit:
                    violations.append(
                        f"{path.relative_to(ROOT)}:{number}: {len(line)} chars"
                    )
    return violations


def _dgs_contract() -> dict[str, object]:
    _add_src()
    from gis2dgs.config import DgsSchemaConfig
    from gis2dgs.dgs import DgsSchema

    forbidden = {"version", "powerfactory_version", "digsilent_version", "dgs_version"}
    domain_fields = set(DgsSchema.__dataclass_fields__)
    config_fields = set(DgsSchemaConfig.model_fields)
    allowed_revision = "dgs_format_version"
    return {
        "version_selector_fields_present": sorted(
            forbidden.intersection(domain_fields | config_fields)
        ),
        "dgs_format_revision_field_present": allowed_revision in domain_fields,
        "product_version_neutral": not forbidden.intersection(domain_fields | config_fields),
    }


def _input_contract() -> dict[str, object]:
    _add_src()
    from gis2dgs.input import InputKind, detect_input_kind

    cases = {
        "network.xlsx": InputKind.EXCEL,
        "network.csv": InputKind.CSV,
        "network.tsv": InputKind.CSV,
        "network.shp": InputKind.VECTOR,
        "network.gpkg": InputKind.VECTOR,
        "network.geojson": InputKind.VECTOR,
        "network.parquet": InputKind.PARQUET,
        "network.sqlite": InputKind.DATABASE,
        "network.bak": InputKind.MSSQL_BACKUP,
        "postgresql+psycopg://host/db": InputKind.DATABASE,
        "mssql+pyodbc://host/db": InputKind.DATABASE,
        "oracle+oracledb://host/db": InputKind.DATABASE,
        "mysql+pymysql://host/db": InputKind.DATABASE,
    }
    failures: list[str] = []
    for source, expected in cases.items():
        try:
            actual = detect_input_kind(source)
        except Exception as exc:  # pragma: no cover - audit utility
            failures.append(f"{source}: {exc!r}")
            continue
        if actual != expected:
            failures.append(f"{source}: expected {expected}, got {actual}")

    product_tokens = re.compile(r"\b(arcgis|igea|qgis)\b", re.IGNORECASE)
    product_specific_source_hits: list[str] = []
    for path in (ROOT / "src").rglob("*.py"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if product_tokens.search(line):
                product_specific_source_hits.append(
                    f"{path.relative_to(ROOT)}:{number}: {line.strip()}"
                )
    return {
        "detection_cases": len(cases),
        "detection_failures": failures,
        "product_specific_source_hits": product_specific_source_hits,
    }


def _secret_scan() -> list[str]:
    findings: list[str] = []
    credential_uri = re.compile(r"\w+(?:\+\w+)?://[^\s:/]+:[^\s@]+@")
    for base in (ROOT / "src", ROOT / "config", ROOT / "examples"):
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".py", ".yaml", ".yml", ".toml"}:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if credential_uri.search(line):
                    findings.append(f"{path.relative_to(ROOT)}:{number}")
    return findings


def _minimal_conversion() -> dict[str, object]:
    output_dir = ROOT / "examples" / "minimal" / "output"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    command = [
        sys.executable,
        "-m",
        "gis2dgs",
        "convert",
        "examples/minimal/project.yaml",
        "--json",
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = output_dir / "minimal_dgs.xlsx"
    return {
        "returncode": result.returncode,
        "output_exists": output.exists(),
        "output_bytes": output.stat().st_size if output.exists() else 0,
        "stdout": result.stdout.strip().splitlines()[-20:],
        "stderr": result.stderr.strip().splitlines()[-20:],
    }


def _external_reference_status() -> dict[str, object]:
    status: dict[str, object] = {}
    bundled = ROOT / "data" / "reference" / "real"
    dgs = os.getenv("GIS2DGS_DGS_REFERENCE") or str(bundled / "SALIDA_DGS.xlsx")
    real_input = os.getenv("GIS2DGS_REAL_INPUT") or str(bundled / "M_ALIMENTAD.xlsx")
    status["dgs_reference"] = dgs if Path(dgs).exists() else None
    status["real_input"] = real_input if Path(real_input).exists() else None
    if status["dgs_reference"] is None and status["real_input"] is None:
        status["executed"] = False
        return status
    env = dict(os.environ)
    env["GIS2DGS_DGS_REFERENCE"] = dgs
    env["GIS2DGS_REAL_INPUT"] = real_input
    env["PYTHONPATH"] = str(SRC)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/integration/test_external_reference_files_v100.py",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    status.update(
        {
            "executed": True,
            "returncode": result.returncode,
            "tail": (result.stdout + result.stderr).strip().splitlines()[-12:],
        }
    )
    return status


def _pytest() -> dict[str, object]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    tail = (result.stdout + result.stderr).strip().splitlines()[-14:]
    return {"returncode": result.returncode, "tail": tail}


def _benchmark(nodes: int) -> dict[str, object]:
    _add_src()
    from gis2dgs.topology import TopologyAnalyzer
    from scripts.benchmark_topology import build_radial_network

    network = build_radial_network(nodes)
    start = time.perf_counter()
    report = TopologyAnalyzer().analyze(network)
    elapsed = time.perf_counter() - start
    return {
        "nodes": nodes,
        "lines": nodes - 1,
        "elapsed_seconds": elapsed,
        "islands": len(report.islands),
        "energized_buses": len(report.energized_buses),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit gis2dgs 1.0 release invariants")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--benchmark-nodes", type=int, default=50_000)
    args = parser.parse_args()

    versions = _project_version()
    module_count, import_errors = _import_modules()
    line_violations = _long_lines()
    compiled = compileall.compile_dir(str(SRC), quiet=1)
    dgs_contract = _dgs_contract()
    input_contract = _input_contract()
    secrets = _secret_scan()
    minimal = _minimal_conversion()
    external = _external_reference_status()
    benchmark = _benchmark(args.benchmark_nodes)
    tests = None if args.skip_tests else _pytest()

    report: dict[str, object] = {
        "versions": versions,
        "versions_consistent": len(set(versions)) == 1,
        "compileall": compiled,
        "module_count": module_count,
        "module_import_errors": import_errors,
        "line_length_violations": line_violations,
        "dgs_contract": dgs_contract,
        "input_contract": input_contract,
        "credential_uri_findings": secrets,
        "minimal_conversion": minimal,
        "external_references": external,
        "benchmark": benchmark,
        "pytest": tests,
    }
    passed = bool(
        report["versions_consistent"]
        and compiled
        and not import_errors
        and not line_violations
        and dgs_contract["product_version_neutral"]
        and dgs_contract["dgs_format_revision_field_present"]
        and not input_contract["detection_failures"]
        and not input_contract["product_specific_source_hits"]
        and not secrets
        and minimal["returncode"] == 0
        and minimal["output_exists"]
        and (not external.get("executed") or external.get("returncode") == 0)
        and (tests is None or tests["returncode"] == 0)
    )
    report["audit_passed"] = passed

    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
