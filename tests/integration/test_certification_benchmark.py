import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_benchmark():
    path = ROOT / "scripts" / "benchmark_converter.py"
    spec = importlib.util.spec_from_file_location("benchmark_converter", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_score_mapping_counts_source_and_fields() -> None:
    benchmark = _load_benchmark()
    payload = {
        "buses": {
            "source": "nodos",
            "fields": {"id": "codigo", "nominal_voltage_kv": "tension"},
        },
        "lines": {"source": "wrong", "fields": {"id": "codigo", "from_bus": "nodo_i"}},
    }
    expected = {
        "buses": {
            "source": "nodos",
            "fields": {"id": "codigo", "nominal_voltage_kv": "tension"},
        },
        "lines": {"source": "tramos", "fields": {"id": "codigo", "from_bus": "nodo_i"}},
    }
    score = benchmark.score_mapping(payload, expected)
    assert score["hits"] == 5
    assert score["total"] == 6
    assert score["misses"] == ["lines.source"]
    assert score["pass"] is False


def test_certification_runtime_has_no_ml_or_domain_infra() -> None:
    benchmark = _load_benchmark()
    report = benchmark.check_runtime_independence()
    assert report["pass"]
    assert report["ml_imports_in_src"] == []
    assert report["domain_infra_imports"] == []
    assert report["requirements"]["pass"]
    assert report["pipeline_networkmodel"]["pass"]


def test_certification_detects_mssql_backup_without_live_server() -> None:
    benchmark = _load_benchmark()
    report = benchmark.check_bak_detection()
    assert report["pass"]
    assert report["suffix_kind"] == "mssql_backup"
    assert report["header_kind"] == "mssql_backup"
    assert report["live_sql_server_required"] is False
    assert report["restore_implemented"] is True
    assert report["engine_provisioner"] == "scripts/ensure_mssql.ps1"


def test_certification_mapping_precision_and_llm_fail_open() -> None:
    benchmark = _load_benchmark()
    report = benchmark.check_mapping_precision()
    assert report["pass"]
    assert report["spanish_like"]["precision"] == 1.0
    assert report["minimal"]["precision"] == 1.0
    assert report["llm_http_skipped_without_url"] is True
    assert report["method"] == "nsga-ii+topsis"


def test_certification_benchmark_passes_end_to_end() -> None:
    benchmark = _load_benchmark()
    report = benchmark.run_certification()
    convert = report["checks"]["inspect_and_convert"]
    assert report["status"] == "PASS"
    assert report["verdict"]["use_deep_learning_runtime"] is False
    assert report["verdict"]["use_local_transformers_runtime"] is False
    assert convert["convert"]["counts"] == benchmark.EXPECTED_MINIMAL
    assert convert["convert"]["dgs_exists"] is True
    assert convert["offline"]["ml_modules_loaded_after_convert"] == []
    assert convert["inspect"]["seconds"] >= 0
    assert convert["convert"]["seconds"] >= 0
