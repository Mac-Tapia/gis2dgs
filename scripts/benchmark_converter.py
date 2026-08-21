from __future__ import annotations

import json
import os
import re
import sys
import time
import tracemalloc
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FORBIDDEN_ML_TOKENS = (
    "torch",
    "tensorflow",
    "keras",
    "huggingface",
    "sentence-transformers",
)
ML_IMPORT = re.compile(
    r"^\s*(?:import|from)\s+(torch|transformers|huggingface_hub|tensorflow|keras)\b",
    re.MULTILINE,
)
INFRA_IMPORT = re.compile(
    r"^\s*(?:import|from)\s+(pandas|geopandas|sqlalchemy|openpyxl|pyodbc)\b",
    re.MULTILINE,
)
EXPECTED_MINIMAL = {"buses": 2, "lines": 1, "loads": 1, "sources": 1, "transformers": 0}
SPANISH_EXPECTED: dict[str, dict[str, Any]] = {
    "buses": {"source": "nodos", "fields": {"id": "codigo", "nominal_voltage_kv": "tension"}},
    "lines": {
        "source": "tramos",
        "fields": {
            "id": "codigo",
            "from_bus": "nodo_i",
            "to_bus": "nodo_f",
            "length_km": "longitud",
            "nominal_voltage_kv": "tension",
        },
    },
    "loads": {
        "source": "cargas",
        "fields": {"id": "codigo", "bus_id": "nodo", "active_power_mw": "potencia"},
    },
    "sources": {
        "source": "alimentadores",
        "fields": {"id": "codigo", "bus_id": "nodo", "nominal_voltage_kv": "tension"},
    },
}
MINIMAL_EXPECTED: dict[str, dict[str, Any]] = {
    "buses": {"source": "buses", "fields": {"id": "id", "nominal_voltage_kv": "voltage_kv"}},
    "lines": {
        "source": "lines",
        "fields": {
            "id": "id",
            "from_bus": "from_bus",
            "to_bus": "to_bus",
            "length_km": "length_km",
            "nominal_voltage_kv": "voltage_kv",
        },
    },
    "loads": {
        "source": "loads",
        "fields": {"id": "id", "bus_id": "bus_id", "active_power_mw": "p_mw"},
    },
    "sources": {
        "source": "sources",
        "fields": {"id": "id", "bus_id": "bus_id", "nominal_voltage_kv": "voltage_kv"},
    },
}


def score_mapping(payload: dict[str, Any], expected: dict[str, dict[str, Any]]) -> dict[str, Any]:
    hits = 0
    total = 0
    misses: list[str] = []
    for entity, spec in expected.items():
        layer = payload.get(entity) or {}
        total += 1
        if isinstance(layer, dict) and layer.get("source") == spec["source"]:
            hits += 1
        else:
            misses.append(f"{entity}.source")
        fields = layer.get("fields") if isinstance(layer, dict) else None
        if not isinstance(fields, dict):
            fields = {}
        for field, column in spec["fields"].items():
            total += 1
            if fields.get(field) == column:
                hits += 1
            else:
                misses.append(f"{entity}.{field}")
    precision = hits / total if total else 0.0
    return {
        "hits": hits,
        "total": total,
        "precision": round(precision, 6),
        "misses": misses,
        "pass": precision >= 1.0,
    }


@contextmanager
def without_llm_env() -> Iterator[None]:
    keys = ("GIS2DGS_LLM_URL", "GIS2DGS_LLM_API_KEY")
    saved = {key: os.environ.pop(key, None) for key in keys}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _mib(nbytes: int) -> float:
    return round(nbytes / (1024 * 1024), 3)


def _scan_python_imports(root: Path, pattern: re.Pattern[str]) -> list[str]:
    hits: list[str] = []
    for path in sorted(root.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if pattern.search(text):
            hits.append(str(path.relative_to(ROOT)))
    return hits


def _requirements_forbid_ml() -> dict[str, Any]:
    texts = [
        (ROOT / "requirements.txt").read_text(encoding="utf-8").lower(),
        (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower(),
    ]
    found = [
        token for token in FORBIDDEN_ML_TOKENS if any(token in text for text in texts)
    ]
    return {"forbidden_hits": found, "pass": not found}


def _pipeline_uses_networkmodel() -> dict[str, Any]:
    text = (SRC / "gis2dgs" / "pipeline.py").read_text(encoding="utf-8")
    required = ("GisToDomainMapper", "NetworkValidator", "PowerFactoryMapper", "DgsMapper")
    missing = [name for name in required if name not in text]
    return {"required": list(required), "missing": missing, "pass": not missing}


def check_runtime_independence() -> dict[str, Any]:
    ml_imports = _scan_python_imports(SRC / "gis2dgs", ML_IMPORT)
    domain_infra = _scan_python_imports(SRC / "gis2dgs" / "domain", INFRA_IMPORT)
    requirements = _requirements_forbid_ml()
    pipeline = _pipeline_uses_networkmodel()
    loaded = [
        name for name in ("torch", "transformers", "huggingface_hub") if name in sys.modules
    ]
    return {
        "ml_imports_in_src": ml_imports,
        "domain_infra_imports": domain_infra,
        "requirements": requirements,
        "pipeline_networkmodel": pipeline,
        "ml_modules_already_loaded": loaded,
        "pass": (
            not ml_imports
            and not domain_infra
            and requirements["pass"]
            and pipeline["pass"]
            and not loaded
        ),
    }


def check_bak_detection() -> dict[str, Any]:
    from gis2dgs.input import InputKind, InputReaderFactory, detect_input_kind
    from gis2dgs.input.readers.mssql_backup import MssqlBackupReader

    suffix_kind = detect_input_kind(Path("network.bak"))
    with TemporaryDirectory() as raw:
        folder = Path(raw)
        nameless = folder / "ELOR25_V1"
        nameless.write_bytes(b"TAPE" + b"\x00" * 40 + "Microsoft SQL".encode("utf-16le"))
        header_kind = detect_input_kind(nameless)
        backup = folder / "red.bak"
        backup.write_bytes(b"TAPE")
        reader = InputReaderFactory.create(backup, kind=InputKind.AUTO)
    return {
        "suffix_kind": suffix_kind.value,
        "header_kind": header_kind.value,
        "reader": type(reader).__name__,
        "live_sql_server_required": False,
        "restore_implemented": True,
        "engine_provisioner": "scripts/ensure_mssql.ps1",
        "pass": (
            suffix_kind is InputKind.MSSQL_BACKUP
            and header_kind is InputKind.MSSQL_BACKUP
            and isinstance(reader, MssqlBackupReader)
        ),
    }


def _spanish_dataset():
    import pandas as pd

    from gis2dgs.input import InputDataset

    dataset = InputDataset()
    dataset.add_table(
        "nodos",
        pd.DataFrame({"codigo": ["B1", "B2"], "nombre": ["A", "B"], "tension": [13.2, 13.2]}),
    )
    dataset.add_table(
        "tramos",
        pd.DataFrame(
            {
                "codigo": ["L1"],
                "nodo_i": ["B1"],
                "nodo_f": ["B2"],
                "longitud": [1.2],
                "tension": [13.2],
            }
        ),
    )
    dataset.add_table(
        "cargas",
        pd.DataFrame({"codigo": ["C1"], "nodo": ["B2"], "potencia": [0.5], "q": [0.1]}),
    )
    dataset.add_table(
        "alimentadores",
        pd.DataFrame({"codigo": ["S1"], "nodo": ["B1"], "tension": [13.2]}),
    )
    return dataset


def check_mapping_precision() -> dict[str, Any]:
    from gis2dgs.assist.llm import refine_mapping_with_llm
    from gis2dgs.assist.service import mapping_to_yaml_payload, suggest_mapping
    from gis2dgs.input import InputKind, InputReaderFactory, discover_schema, merge_datasets

    with without_llm_env():
        llm_skipped = refine_mapping_with_llm({"tables": []}, {}) is None
        spanish = suggest_mapping(
            discover_schema(_spanish_dataset()),
            seed=1,
            population_size=16,
            generations=8,
            use_llm=True,
        )
        spanish_score = score_mapping(
            mapping_to_yaml_payload(spanish.mapping), SPANISH_EXPECTED
        )

        datasets = []
        for table in ("buses", "lines", "loads", "sources"):
            path = ROOT / "examples" / "minimal" / "input" / f"{table}.csv"
            datasets.append(
                InputReaderFactory.create(
                    path,
                    kind=InputKind.CSV,
                    source_id=table,
                    options={"table_name": table},
                ).read()
            )
        minimal = suggest_mapping(
            discover_schema(merge_datasets(datasets, on_conflict="overwrite")),
            seed=42,
            population_size=16,
            generations=8,
            use_llm=True,
        )
        minimal_score = score_mapping(
            mapping_to_yaml_payload(minimal.mapping), MINIMAL_EXPECTED
        )
    return {
        "spanish_like": spanish_score,
        "minimal": minimal_score,
        "llm_http_skipped_without_url": llm_skipped,
        "method": spanish.report.get("method"),
        "pass": spanish_score["pass"] and minimal_score["pass"] and llm_skipped,
    }


def check_inspect_and_convert() -> dict[str, Any]:
    from gis2dgs.cli.workspace import classify_file, execute_loaded_file
    from gis2dgs.config import load_project_config
    from gis2dgs.pipeline import run_conversion

    inspect_path = ROOT / "examples" / "minimal" / "input"
    project_path = ROOT / "examples" / "minimal" / "project.yaml"

    tracemalloc.start()
    inspect_start = time.perf_counter()
    inspect_outcome = execute_loaded_file(classify_file(inspect_path))
    inspect_seconds = time.perf_counter() - inspect_start
    _, inspect_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    with without_llm_env():
        tracemalloc.start()
        convert_start = time.perf_counter()
        result = run_conversion(load_project_config(project_path))
        convert_seconds = time.perf_counter() - convert_start
        _, convert_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

    counts = {
        "buses": result.buses,
        "lines": result.lines,
        "loads": result.loads,
        "sources": result.sources,
        "transformers": result.transformers,
    }
    correctness_pass = counts == EXPECTED_MINIMAL and result.output_dgs.exists()
    ml_names = ("torch", "transformers", "huggingface_hub")
    ml_loaded = [name for name in ml_names if name in sys.modules]
    return {
        "inspect": {
            "success": inspect_outcome.success,
            "action": inspect_outcome.action,
            "seconds": round(inspect_seconds, 6),
            "tracemalloc_peak_mib": _mib(inspect_peak),
        },
        "convert": {
            "seconds": round(convert_seconds, 6),
            "tracemalloc_peak_mib": _mib(convert_peak),
            "output_dgs": str(result.output_dgs),
            "dgs_exists": result.output_dgs.exists(),
            "counts": counts,
            "expected": EXPECTED_MINIMAL,
        },
        "offline": {
            "llm_env_cleared": True,
            "ml_modules_loaded_after_convert": ml_loaded,
            "pass": not ml_loaded,
        },
        "pass": inspect_outcome.success and correctness_pass and not ml_loaded,
    }


def run_certification() -> dict[str, Any]:
    independence = check_runtime_independence()
    bak = check_bak_detection()
    mapping = check_mapping_precision()
    pipeline = check_inspect_and_convert()
    checks = {
        "runtime_independence": independence,
        "mssql_backup_detection": bak,
        "mapping_precision": mapping,
        "inspect_and_convert": pipeline,
    }
    passed = all(item["pass"] for item in checks.values())
    return {
        "status": "PASS" if passed else "FAIL",
        "verdict": {
            "use_deep_learning_runtime": False,
            "use_local_transformers_runtime": False,
            "mapping_assist": "nsga-ii+topsis",
            "optional_llm": "HTTP GIS2DGS_LLM_URL (stdlib, fail-open, mapping only)",
        },
        "checks": checks,
        "notes": {
            "tracemalloc": (
                "Peak Python allocations only; pandas/openpyxl native RSS is not included."
            ),
            "bak": (
                "Detection is certified without a live engine. Restore is implemented; "
                "scripts/ensure_mssql.ps1 provisions or detects SQL Server for a live restore."
            ),
        },
    }


def main() -> None:
    report = run_certification()
    output = ROOT / "output" / "certification_benchmark.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    output.write_text(text, encoding="utf-8")
    print(text)
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
