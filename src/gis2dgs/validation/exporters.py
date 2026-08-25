import csv
import json
from pathlib import Path

from .result import ValidationReport


class ValidationReportWriter:
    """Serialize validation results without coupling validation to pandas or a database."""

    MAX_ISSUES = 5_000

    @staticmethod
    def write_json(report: ValidationReport, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        issues = list(report.issues)
        truncated = len(issues) > ValidationReportWriter.MAX_ISSUES
        if truncated:
            issues = issues[: ValidationReportWriter.MAX_ISSUES]
        payload = {
            "summary": report.summary(),
            "issues_truncated": truncated,
            "issues_written": len(issues),
            "issues": [issue.as_dict() for issue in issues],
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
        issues = list(report.issues)
        if len(issues) > ValidationReportWriter.MAX_ISSUES:
            issues = issues[: ValidationReportWriter.MAX_ISSUES]
        with destination.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for issue in issues:
                writer.writerow(issue.as_dict())
        return destination
