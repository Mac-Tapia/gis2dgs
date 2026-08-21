from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from gis2dgs.topology.models import TopologyReport


class Severity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ValidationCategory(StrEnum):
    STRUCTURE = "STRUCTURE"
    DATA_QUALITY = "DATA_QUALITY"
    ELECTRICAL = "ELECTRICAL"
    LIBRARY = "LIBRARY"
    TOPOLOGY = "TOPOLOGY"
    READINESS = "READINESS"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    severity: Severity
    message: str
    object_id: str | None = None
    category: ValidationCategory = ValidationCategory.STRUCTURE
    object_type: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "category": self.category.value,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "message": self.message,
        }


@dataclass(slots=True)
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)
    topology: TopologyReport | None = None
    profile: str = "standard"

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == Severity.WARNING]

    @property
    def infos(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == Severity.INFO]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def info_count(self) -> int:
        return len(self.infos)

    def by_category(self, category: ValidationCategory) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.category == category]

    def summary(self) -> dict[str, Any]:
        severity_counts = Counter(issue.severity.value for issue in self.issues)
        category_counts = Counter(issue.category.value for issue in self.issues)
        code_counts = Counter(issue.code for issue in self.issues)
        return {
            "profile": self.profile,
            "valid": self.is_valid,
            "issues": len(self.issues),
            "errors": severity_counts.get(Severity.ERROR.value, 0),
            "warnings": severity_counts.get(Severity.WARNING.value, 0),
            "info": severity_counts.get(Severity.INFO.value, 0),
            "categories": dict(sorted(category_counts.items())),
            "codes": dict(sorted(code_counts.items())),
        }
