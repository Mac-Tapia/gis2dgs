from pathlib import Path

from gis2dgs.cli.workspace import load_and_run

ROOT = Path(__file__).resolve().parents[3]


def test_load_and_run_emits_progress_steps(tmp_path: Path) -> None:
    steps: list[str] = []

    outcome = load_and_run(
        ROOT / "examples" / "minimal" / "project.yaml",
        work_dir=tmp_path / "run",
        on_progress=steps.append,
    )
    assert outcome.success
    joined = "\n".join(steps)
    assert "Inicio" in joined
    assert "[1/8]" in joined
    assert "[8/8]" in joined or "DGS escrito" in joined
