from __future__ import annotations

import compileall
import importlib
import json
import pkgutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

REQUIRED = [
    "START_HERE.md",
    "AGENTS.md",
    "skills/gis2dgs/SKILL.md",
    "docs/INTEGRAL_MANUAL.md",
    "docs/SYSTEM_REQUIREMENTS.md",
    "docs/PROJECT_MAP.md",
    "docs/MANUAL_EJECUCION_CONSOLA.md",
    "docs/GUIA_PASO_A_PASO.md",
    "docs/CERTIFICATION_BENCHMARK.md",
    "PROJECT_MANIFEST.yaml",
    "requirements.txt",
    "requirements-lock.txt",
    "pyproject.toml",
    "src/gis2dgs/pipeline.py",
    "scripts/benchmark_converter.py",
    "tests",
    "examples/minimal/project.yaml",
    "examples/mssql_backup/project.yaml",
    "examples/mssql_backup/config/mapping.yaml",
    "scripts/ensure_mssql.ps1",
    "scripts/mssql_backup_roundtrip.py",
    "docker-compose.mssql.yml",
    "RUN.ps1",
    "data/reference/real/SALIDA_DGS.xlsx",
    "data/reference/real/M_ALIMENTAD.xlsx",
]


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> None:
    missing = [item for item in REQUIRED if not (ROOT / item).exists()]
    if missing:
        fail("Faltan archivos requeridos: " + ", ".join(missing))

    manifest = yaml.safe_load((ROOT / "PROJECT_MANIFEST.yaml").read_text(encoding="utf-8"))
    if manifest["project"]["version"] != "1.0.0":
        fail("PROJECT_MANIFEST.yaml no coincide con la release 1.0.0")

    import gis2dgs
    if gis2dgs.__version__ != "1.0.0":
        fail(f"Versión Python inesperada: {gis2dgs.__version__}")

    settings = yaml.safe_load((ROOT / "config/settings.yaml").read_text(encoding="utf-8"))
    if settings["project"]["version"] != gis2dgs.__version__:
        fail("config/settings.yaml y gis2dgs.__version__ no coinciden")

    if not compileall.compile_dir(str(SRC), quiet=1):
        fail("compileall falló en src/")

    package = importlib.import_module("gis2dgs")
    errors: list[str] = []
    imported = 0
    for module in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        try:
            importlib.import_module(module.name)
            imported += 1
        except Exception as exc:  # pragma: no cover - release audit path
            errors.append(f"{module.name}: {type(exc).__name__}: {exc}")
    if errors:
        fail("Errores importando módulos:\n" + "\n".join(errors))

    forbidden = ["arcgis", "igea", "qgis"]
    hits: list[str] = []
    for py_file in SRC.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="ignore").lower()
        for token in forbidden:
            if token in text:
                hits.append(f"{py_file.relative_to(ROOT)} -> {token}")
    if hits:
        fail("Dependencias de marca detectadas en src/: " + "; ".join(hits))

    report = {
        "status": "PASS",
        "version": gis2dgs.__version__,
        "required_files": len(REQUIRED),
        "imported_modules": imported,
        "brand_dependencies_in_src": 0,
        "real_reference_files": 2,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
