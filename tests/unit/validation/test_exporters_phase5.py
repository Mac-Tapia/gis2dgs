import csv
import json
from pathlib import Path

from gis2dgs.validation import (
    Severity,
    ValidationIssue,
    ValidationReport,
    ValidationReportWriter,
)


def _report() -> ValidationReport:
    return ValidationReport(
        issues=[ValidationIssue("X001", Severity.ERROR, "Problem", object_id="B1")]
    )


def test_write_json(tmp_path: Path) -> None:
    path = ValidationReportWriter.write_json(_report(), tmp_path / "report.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["summary"]["errors"] == 1
    assert data["issues"][0]["code"] == "X001"


def test_write_csv(tmp_path: Path) -> None:
    path = ValidationReportWriter.write_csv(_report(), tmp_path / "report.csv")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["code"] == "X001"
    assert rows[0]["object_id"] == "B1"
