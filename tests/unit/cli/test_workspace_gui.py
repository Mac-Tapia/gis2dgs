from pathlib import Path

import pytest
import yaml

from gis2dgs.cli.main import build_parser
from gis2dgs.cli.workspace import (
    LoadedFileKind,
    classify_file,
    classify_paths,
    detect_project_sources,
    execute_loaded_file,
    load_and_run,
    load_and_run_loaded,
    suggest_mapping_for_loaded,
)
from gis2dgs.config import load_project_config
from gis2dgs.input import SQL_SCRIPT_ERROR

ROOT = Path(__file__).resolve().parents[3]


def test_cli_parser_has_program_name() -> None:
    assert build_parser().prog == "gis2dgs"


def test_cli_parser_has_gui_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["gui", "--no-prompt"])
    assert args.command == "gui"
    assert args.no_prompt is True
    assert args.prompt is False


def test_cli_parser_gui_prompt_opt_in() -> None:
    parser = build_parser()
    args = parser.parse_args(["gui", "--prompt"])
    assert args.command == "gui"
    assert args.prompt is True


def test_cli_parser_has_suggest_mapping() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["suggest-mapping", "datos.xlsx", "--output", "output/mapping.yaml"]
    )
    assert args.command == "suggest-mapping"
    assert args.llm is False


def test_cli_parser_has_load_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["load", "datos.xlsx", "--json"])
    assert args.command == "load"
    assert args.as_json is True


def test_classify_minimal_project() -> None:
    loaded = classify_file(ROOT / "examples" / "minimal" / "project.yaml")
    assert loaded.kind is LoadedFileKind.PROJECT
    assert "minimal" in loaded.label.lower() or loaded.kind.value == "project"
    ids = {row["id"] for row in loaded.detections}
    assert ids == {"buses", "lines", "loads", "sources"}
    assert all(row["status"] == "ok" for row in loaded.detections)
    assert all(row["detected_kind"] == "csv" for row in loaded.detections)


def test_classify_project_folder_detects_yaml() -> None:
    loaded = classify_file(ROOT / "examples" / "minimal")
    assert loaded.kind is LoadedFileKind.PROJECT
    assert loaded.detections


def test_classify_input_folder_detects_all_csv() -> None:
    loaded = classify_file(ROOT / "examples" / "minimal" / "input")
    assert loaded.kind is LoadedFileKind.INPUT
    names = {path.name for path in loaded.members}
    assert names == {"buses.csv", "lines.csv", "loads.csv", "sources.csv"}


def test_classify_paths_cymdist_bundle() -> None:
    fixtures = ROOT / "tests" / "fixtures" / "cymdist"
    loaded = classify_paths(
        (
            fixtures / "RED_030826_SAMPLE.txt",
            fixtures / "CARGA_030826_SAMPLE.txt",
            fixtures / "BD_Equipo_V26.txt",
        )
    )
    assert loaded.kind is LoadedFileKind.INPUT
    assert len(loaded.members) == 3
    assert "Paquete" in loaded.label
    assert "Análisis de paquete" in loaded.detail
    assert any(row.get("status") == "companion" for row in loaded.detections)


def test_load_and_run_loaded_preserves_explicit_members(tmp_path: Path) -> None:
    fixtures = ROOT / "tests" / "fixtures" / "cymdist"
    loaded = classify_paths(
        (
            fixtures / "RED_030826_SAMPLE.txt",
            fixtures / "CARGA_030826_SAMPLE.txt",
        )
    )
    outcome = load_and_run_loaded(loaded, work_dir=tmp_path / "run", sample_rows=0)
    assert outcome.success
    assert outcome.payload["conversion"]["network"]["lines"] >= 2
    assert outcome.payload["conversion"]["network"]["loads"] >= 1


def test_detect_project_sources_uses_programmed_detector() -> None:
    project = load_project_config(ROOT / "examples" / "minimal" / "project.yaml")
    rows = detect_project_sources(project)
    assert len(rows) == 4
    assert {row["detected_kind"] for row in rows} == {"csv"}


def test_classify_input_csv() -> None:
    loaded = classify_file(ROOT / "examples" / "minimal" / "input" / "buses.csv")
    assert loaded.kind is LoadedFileKind.INPUT


def test_classify_mapping_yaml_is_not_executable_project() -> None:
    loaded = classify_file(ROOT / "examples" / "minimal" / "config" / "mapping.yaml")
    assert loaded.kind is LoadedFileKind.UNSUPPORTED


def test_classify_real_dgs_template() -> None:
    loaded = classify_file(ROOT / "data" / "reference" / "real" / "SALIDA_DGS.xlsx")
    assert loaded.kind is LoadedFileKind.DGS_TEMPLATE


def test_classify_real_input_excel() -> None:
    loaded = classify_file(ROOT / "data" / "reference" / "real" / "M_ALIMENTAD.xlsx")
    assert loaded.kind is LoadedFileKind.INPUT


def test_classify_sql_script_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "red.sql"
    path.write_text("SELECT 1;", encoding="utf-8")
    loaded = classify_file(path)
    assert loaded.kind is LoadedFileKind.UNSUPPORTED
    assert loaded.detail == SQL_SCRIPT_ERROR


def test_classify_sql_server_backup_without_extension(tmp_path: Path) -> None:
    path = tmp_path / "ELOR25_V1"
    path.write_bytes(b"TAPE" + b"\x00" * 40 + "Microsoft SQL".encode("utf-16le"))
    loaded = classify_file(path)
    assert loaded.kind is LoadedFileKind.INPUT
    assert loaded.label == "Backup SQL Server"
    assert loaded.members == (path.resolve(),)
    assert "SQL Server" in loaded.detail
    assert "Docker" in loaded.detail or "docker" in loaded.detail.lower()


def test_execute_minimal_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    loaded = classify_file(ROOT / "examples" / "minimal" / "project.yaml")
    outcome = execute_loaded_file(loaded)
    assert outcome.success
    assert outcome.action == "convert"
    assert outcome.payload["network"]["buses"] == 2
    assert Path(str(outcome.payload["output_dgs"])).exists()


def test_execute_inspect_input(tmp_path: Path) -> None:
    loaded = classify_file(ROOT / "examples" / "minimal" / "input" / "buses.csv")
    output = tmp_path / "schema.yaml"
    outcome = execute_loaded_file(loaded, output=output)
    assert outcome.success
    assert outcome.action == "inspect-input"
    assert output.exists()
    assert "buses" in output.read_text(encoding="utf-8")


def test_suggest_mapping_on_minimal_input_folder(tmp_path: Path) -> None:
    loaded = classify_file(ROOT / "examples" / "minimal" / "input")
    output = tmp_path / "mapping.yaml"
    outcome = suggest_mapping_for_loaded(loaded, output=output, sample_rows=0)
    assert outcome.success
    assert outcome.action == "suggest-mapping"
    mapping = outcome.payload["mapping"]
    assert isinstance(mapping, dict)
    assert mapping["buses"]["source"] == "buses"
    assert mapping["lines"]["fields"]["from_bus"] == "from_bus"
    assert output.exists()
    assert output.with_name("mapping_report.yaml").exists()


def test_load_and_run_minimal_input_folder_writes_dgs(tmp_path: Path) -> None:
    outcome = load_and_run(
        ROOT / "examples" / "minimal" / "input",
        work_dir=tmp_path / "run",
        sample_rows=0,
    )
    assert outcome.success
    assert outcome.action == "load"
    conversion = outcome.payload["conversion"]
    assert conversion["network"]["buses"] == 2
    assert Path(str(conversion["output_dgs"])).exists()
    assert (tmp_path / "run" / "project.yaml").is_file()


def test_load_and_run_project_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    outcome = load_and_run(ROOT / "examples" / "minimal" / "project.yaml")
    assert outcome.success
    assert outcome.action == "convert"
    assert outcome.payload["network"]["buses"] == 2


def test_load_and_run_project_yaml_fails_when_sources_not_ready(
    tmp_path: Path,
) -> None:
    project = yaml.safe_load(
        (ROOT / "examples" / "minimal" / "project.yaml").read_text(encoding="utf-8")
    )
    project["inputs"]["sources"][0]["uri"] = "input/no_existe.csv"
    broken = tmp_path / "project.yaml"
    broken.write_text(
        yaml.safe_dump(project, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    outcome = load_and_run(broken)
    assert not outcome.success
    assert outcome.action == "convert"
    assert "no es ejecutable" in outcome.message.lower()
    assert "sin conectividad" in outcome.message.lower()
    assert outcome.payload["detected_sources"][0]["status"] == "missing"


def test_load_and_run_database_uri_writes_schema_and_project(tmp_path: Path) -> None:
    db_path = tmp_path / "grid.sqlite"
    source = f"sqlite:///{db_path.as_posix()}"
    from sqlalchemy import create_engine, text

    engine = create_engine(source)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE buses (id TEXT, name TEXT, nominal_voltage_kv REAL, in_service TEXT)"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE lines (id TEXT, name TEXT, from_bus TEXT, to_bus TEXT, length_km REAL, voltage_kv REAL, type_id TEXT, in_service TEXT)"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE loads (id TEXT, name TEXT, bus_id TEXT, p_mw REAL, q_mvar REAL, in_service TEXT)"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE sources (id TEXT, name TEXT, bus_id TEXT, voltage_kv REAL, in_service TEXT)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO buses VALUES ('B1', 'Bus 1', 10.0, 'true'), ('B2', 'Bus 2', 10.0, 'true')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO lines VALUES ('L1', 'Linea 1', 'B1', 'B2', 0.7, 10.0, 'LT1', 'true')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO loads VALUES ('LD1', 'Carga 1', 'B2', 1.0, 0.2, 'true')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO sources VALUES ('S1', 'Fuente 1', 'B1', 10.0, 'true')"
                )
            )
    finally:
        engine.dispose()

    outcome = load_and_run(source, work_dir=tmp_path / "run", sample_rows=0)
    assert outcome.success
    assert outcome.action == "load"
    assert "schema" in outcome.payload
    assert Path(str(outcome.payload["project"])).is_file()
    conversion = outcome.payload["conversion"]
    assert conversion["network"]["buses"] == 2
    assert Path(str(conversion["output_dgs"])).exists()


def test_execute_inspect_dgs_template(tmp_path: Path) -> None:
    loaded = classify_file(ROOT / "data" / "reference" / "real" / "SALIDA_DGS.xlsx")
    output = tmp_path / "dgs.yaml"
    outcome = execute_loaded_file(loaded, output=output)
    assert outcome.success
    assert outcome.action == "inspect-template"
    assert "StaCubic" in output.read_text(encoding="utf-8")


def test_load_and_run_without_buses_does_not_write_dgs(tmp_path: Path) -> None:
    source = tmp_path / "solo_alimentador.xlsx"
    import pandas as pd

    pd.DataFrame(
        {
            "id": [1],
            "codigo": ["AL01"],
            "tension": ["13.2"],
            "conexionn": ["B1"],
        }
    ).to_excel(source, index=False, sheet_name="M_ALIMENTAD")
    outcome = load_and_run(source, work_dir=tmp_path / "run", sample_rows=0)
    assert not outcome.success
    assert "barras" in outcome.message.lower()
    assert "conversion" not in outcome.payload
    assert Path(str(outcome.payload["project"])).is_file()
