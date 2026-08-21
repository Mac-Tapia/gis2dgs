import csv
import json
from pathlib import Path

from .result import ValidationReport


class ValidationReportWriter:
    """Serialize validation results without coupling validation to pandas or a database."""

    @staticmethod
    def write_json(report: ValidationReport, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "summary": report.summary(),
            "issues": [issue.as_dict() for issue in report.issues],
        }
        destination.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return destination

    @staticmethod
    def write_csv(report: ValidationReport, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "code",
            "severity",
            "category",
            "object_type",
            "object_id",
            "message",
        ]
        with destination.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for issue in report.issues:
                writer.writerow(issue.as_dict())
        return destination
