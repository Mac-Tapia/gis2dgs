from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_integral_agent_and_manual_files_exist() -> None:
    expected = [
        ROOT / "START_HERE.md",
        ROOT / "AGENTS.md",
        ROOT / "skills" / "gis2dgs" / "SKILL.md",
        ROOT / "docs" / "INTEGRAL_MANUAL.md",
        ROOT / "docs" / "MANUAL_EJECUCION_CONSOLA.md",
        ROOT / "docs" / "GUIA_PASO_A_PASO.md",
        ROOT / "docs" / "CERTIFICATION_BENCHMARK.md",
        ROOT / "docs" / "SYSTEM_REQUIREMENTS.md",
        ROOT / "PROJECT_MANIFEST.yaml",
        ROOT / "INSTALL_AND_VERIFY.ps1",
        ROOT / "RUN.ps1",
    ]
    assert all(path.is_file() for path in expected)


def test_step_by_step_guide_covers_load_to_convert() -> None:
    text = (ROOT / "docs" / "GUIA_PASO_A_PASO.md").read_text(encoding="utf-8")
    assert "Cargar archivo" in text
    assert "Ejecutar" in text
    assert ".\\RUN.ps1" in text
    assert "python -m gis2dgs" in text
    assert "inspect-input" in text
    assert "M_ALIMENTAD.xlsx" in text
    assert "examples\\minimal\\project.yaml" in text
    assert "convert examples\\minimal\\project.yaml" in text
    assert "convert output\\mi_proyecto\\project.yaml" in text
    assert "validation.json" in text
    assert "File > Import > DGS" in text
    assert ".sql" in text
    assert "Cargar carpeta" in text
    assert ".shp" in text
    assert "ELOR25_V1" in text
    assert "mssql_backup" in text
    assert "ensure_mssql.ps1" in text
    assert "suggest-mapping" in text
    assert "Proponer mapping" in text
    assert "python -m gis2dgs load" in text


def test_certification_benchmark_is_part_of_the_integral_contract() -> None:
    script = ROOT / "scripts" / "benchmark_converter.py"
    doc = ROOT / "docs" / "CERTIFICATION_BENCHMARK.md"
    assert script.is_file()
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    assert "No." in text
    assert "torch" in text.lower()
    assert "nsga" in text.lower()
    assert "examples/minimal" in text or "examples\\minimal" in text
    source = script.read_text(encoding="utf-8")
    assert "GIS2DGS_LLM_URL" in source
    assert "mssql_backup" in source
    assert "tracemalloc" in source


def test_integral_requirements_declares_supported_connectors_and_quality_tools() -> None:
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    for requirement in (
        "pandas",
        "geopandas",
        "networkx",
        "openpyxl",
        "psycopg",
        "pyodbc",
        "oracledb",
        "pymysql",
        "pyarrow",
        "xlrd",
        "pytest",
        "pytest-cov",
        "ruff",
        "mypy",
        "build",
        "wheel",
    ):
        assert requirement in text
    for forbidden in ("torch", "tensorflow", "keras", "huggingface", "sentence-transformers"):
        assert forbidden not in text


def test_integral_manifest_points_to_bundled_real_references() -> None:
    manifest = yaml.safe_load((ROOT / "PROJECT_MANIFEST.yaml").read_text(encoding="utf-8"))
    references = manifest["project"]["real_references"]
    assert references
    assert all((ROOT / reference).is_file() for reference in references)
