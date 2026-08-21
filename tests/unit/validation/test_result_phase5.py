from gis2dgs.validation import (
    Severity,
    ValidationCategory,
    ValidationIssue,
    ValidationReport,
)


def test_validation_report_summary_and_categories() -> None:
    report = ValidationReport(
        issues=[
            ValidationIssue(
                "NET001",
                Severity.ERROR,
                "bad reference",
                category=ValidationCategory.STRUCTURE,
            ),
            ValidationIssue(
                "TOP001",
                Severity.WARNING,
                "isolated",
                category=ValidationCategory.TOPOLOGY,
            ),
            ValidationIssue(
                "TOP007",
                Severity.INFO,
                "boundary",
                category=ValidationCategory.TOPOLOGY,
            ),
        ],
        profile="standard",
    )

    assert not report.is_valid
    assert report.error_count == 1
    assert report.warning_count == 1
    assert report.info_count == 1
    assert len(report.by_category(ValidationCategory.TOPOLOGY)) == 2
    assert report.summary()["codes"] == {"NET001": 1, "TOP001": 1, "TOP007": 1}
