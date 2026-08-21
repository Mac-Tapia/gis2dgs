from pathlib import Path

import pytest

from gis2dgs.cli.workspace import classify_file, classify_paths, load_and_run
from gis2dgs.config import load_project_config
from gis2dgs.pipeline import run_conversion

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "cymdist"
REAL_BUNDLE = Path(r"D:\BaseDatosElectroDunas\bdnuevo")
REAL_IGEA = Path(r"D:\BaseDatosElectroDunas\BaseDatosIGEA")


def test_classify_cymdist_folder_lists_bundle_summary() -> None:
    loaded = classify_file(FIXTURES)
    assert loaded.kind.value == "input"
    assert len(loaded.members) == 3
    assert "Análisis de paquete" in loaded.detail
    assert "distribution" in loaded.detail.lower() or "Vinculados" in loaded.detail


def test_classify_paths_explicit_selection() -> None:
    loaded = classify_paths(
        (
            FIXTURES / "RED_030826_SAMPLE.txt",
            FIXTURES / "CARGA_030826_SAMPLE.txt",
            FIXTURES / "BD_Equipo_V26.txt",
        )
    )
    assert loaded.kind.value == "input"
    assert {path.name for path in loaded.members} == {
        "RED_030826_SAMPLE.txt",
        "CARGA_030826_SAMPLE.txt",
        "BD_Equipo_V26.txt",
    }
    assert "Análisis de paquete" in loaded.detail


def test_convert_cymdist_example_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    project = load_project_config(ROOT / "examples" / "cymdist_030826" / "project.yaml")
    result = run_conversion(project)
    assert result.lines == 2
    assert result.buses == 3
    assert result.loads == 1
    assert result.sources == 1
    assert result.output_dgs.exists()


def test_load_and_run_cymdist_fixture_folder(tmp_path: Path) -> None:
    outcome = load_and_run(FIXTURES, work_dir=tmp_path / "run", sample_rows=0)
    assert outcome.success
    assert "conversion" in outcome.payload
    assert outcome.payload["conversion"]["network"]["lines"] >= 2


@pytest.mark.skipif(not REAL_BUNDLE.is_dir(), reason="Real CYMDIST bundle not available locally")
def test_assess_real_igea_cymdist_exports() -> None:
    from gis2dgs.input import assess_input_bundle

    paths = tuple(REAL_BUNDLE.glob("*.txt"))
    assessment = assess_input_bundle(paths)
    assert assessment.linked is True
    assert assessment.system_kind in {"distribution", "mixed"}
    assert assessment.cross_reference_ratio is not None
    assert assessment.cross_reference_ratio > 0.9


@pytest.mark.skipif(not REAL_IGEA.is_dir(), reason="BaseDatosIGEA bundle not available locally")
def test_classify_real_basedatos_igea_folder() -> None:
    loaded = classify_file(REAL_IGEA)
    assert loaded.kind.value == "input"
    names = {path.name for path in loaded.members}
    assert "RED_030826.txt" in names
    assert "CARGA_030826.txt" in names
    assert "Análisis de paquete" in loaded.detail
    assert "Vinculados: sí" in loaded.detail


@pytest.mark.skipif(not REAL_IGEA.is_dir(), reason="BaseDatosIGEA bundle not available locally")
def test_classify_paths_real_basedatos_igea_selection() -> None:
    loaded = classify_paths(
        (
            REAL_IGEA / "RED_030826.txt",
            REAL_IGEA / "CARGA_030826.txt",
            REAL_IGEA / "BD_Equipo_V26.txt",
        )
    )
    assert loaded.kind.value == "input"
    assert len(loaded.members) == 3
    assert "Vinculados: sí" in loaded.detail
