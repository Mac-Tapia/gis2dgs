from pathlib import Path

from openpyxl import Workbook

from gis2dgs.cli.main import main


def test_cli_inspect_template_writes_yaml(tmp_path: Path, monkeypatch) -> None:
    template = tmp_path / "template.xlsx"
    output = tmp_path / "inspection.yaml"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "ElmTerm"
    sheet.append(["FID", "loc_name"])
    workbook.save(template)
    workbook.close()

    monkeypatch.setattr(
        "sys.argv",
        [
            "gis2dgs",
            "dgs",
            "inspect-template",
            str(template),
            "--output",
            str(output),
        ],
    )
    main()

    text = output.read_text(encoding="utf-8")
    assert "ElmTerm" in text
    assert "FID" in text
