from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .models import DgsDocument
from .schema import DgsSchema


class DgsSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True, slots=True)
class DgsValidationIssue:
    code: str
    severity: DgsSeverity
    message: str
    table: str | None = None
    object_key: str | None = None


@dataclass(frozen=True, slots=True)
class DgsValidationReport:
    issues: tuple[DgsValidationIssue, ...]

    @property
    def errors(self) -> tuple[DgsValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == DgsSeverity.ERROR)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def validate_dgs_document(
    document: DgsDocument,
    schema: DgsSchema,
) -> DgsValidationReport:
    issues: list[DgsValidationIssue] = []
    object_keys: set[str] = set()

    expected_tables = {mapping.table for mapping in schema.classes.values()}
    missing_tables = expected_tables.difference(document.tables)
    for table in sorted(missing_tables):
        issues.append(
            DgsValidationIssue(
                code="DGS001",
                severity=DgsSeverity.ERROR,
                table=table,
                message=f"Configured DGS table {table!r} is missing from the document.",
            )
        )

    for table_name, table in document.tables.items():
        for row in table.rows:
            if row.object_key in object_keys:
                issues.append(
                    DgsValidationIssue(
                        code="DGS002",
                        severity=DgsSeverity.ERROR,
                        table=table_name,
                        object_key=row.object_key,
                        message=f"Duplicate DGS object key: {row.object_key}",
                    )
                )
            object_keys.add(row.object_key)

            unknown = set(row.values).difference(table.columns)
            if unknown:
                issues.append(
                    DgsValidationIssue(
                        code="DGS003",
                        severity=DgsSeverity.ERROR,
                        table=table_name,
                        object_key=row.object_key,
                        message=f"Row contains unknown columns: {sorted(unknown)}",
                    )
                )

    reference_columns = _reference_columns(schema)
    for table_name, columns in reference_columns.items():
        table = document.tables.get(table_name)
        if table is None:
            continue
        for row in table.rows:
            for column in columns:
                target = row.values.get(column)
                if target is None or str(target).strip() == "":
                    continue
                if str(target) not in object_keys:
                    issues.append(
                        DgsValidationIssue(
                            code="DGS004",
                            severity=DgsSeverity.ERROR,
                            table=table_name,
                            object_key=row.object_key,
                            message=(
                                f"Dangling DGS reference {column}={target!r} "
                                f"in table {table_name!r}."
                            ),
                        )
                    )

    return DgsValidationReport(tuple(issues))


def _reference_columns(schema: DgsSchema) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for mapping in schema.classes.values():
        columns = [item.column for item in mapping.references.values()]
        if columns:
            grouped.setdefault(mapping.table, []).extend(columns)
    return {name: tuple(dict.fromkeys(values)) for name, values in grouped.items()}
