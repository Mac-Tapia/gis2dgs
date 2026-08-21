from pathlib import Path

from openpyxl import Workbook

from gis2dgs.dgs import inspect_excel_template


def test_inspector_finds_candidate_headers(tmp_path: Path) -> None:
    path = tmp_path / "template.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "ElmTerm"
    sheet.append(["metadata"])
    sheet.append(["FID", "loc_name", "uknom"])
    workbook.save(path)
    workbook.close()

    report = inspect_excel_template(path)

    assert report.sheets[0].sheet == "ElmTerm"
    assert report.sheets[0].header_row == 2
    assert report.sheets[0].columns == ("FID", "loc_name", "uknom")
