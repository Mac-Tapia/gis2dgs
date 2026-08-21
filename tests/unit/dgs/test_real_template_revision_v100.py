from pathlib import Path

from openpyxl import Workbook

from gis2dgs.dgs import inspect_excel_template


def test_template_inspector_reads_dgs_format_revision(tmp_path: Path) -> None:
    path = tmp_path / "dgs.xlsx"
    workbook = Workbook()
    general = workbook.active
    general.title = "General"
    general.append(["ID(a:40)", "Descr(a:40)", "Val(a:40)"])
    general.append([1, "Version", 5])
    term = workbook.create_sheet("ElmTerm")
    term.append(["ID(a:40)", "loc_name(a:40)", "uknom(r)"])
    workbook.save(path)

    report = inspect_excel_template(path)

    assert report.dgs_format_version == "5"
    assert report.sheets[1].definitions[2].name == "uknom"
