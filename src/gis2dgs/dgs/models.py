from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class DgsRow:
    """One row ready for serialization into a configured DGS table."""

    object_key: str
    values: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.object_key.strip():
            raise ValueError("DGS row object_key cannot be empty.")


@dataclass(slots=True)
class DgsTable:
    """Rows belonging to one DGS table/sheet."""

    name: str
    columns: tuple[str, ...]
    rows: list[DgsRow] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("DGS table name cannot be empty.")
        if len(set(self.columns)) != len(self.columns):
            raise ValueError(f"DGS table {self.name!r} has duplicate columns.")

    def add(self, row: DgsRow) -> None:
        unknown = set(row.values).difference(self.columns)
        if unknown:
            raise ValueError(
                f"DGS row {row.object_key!r} contains columns not declared by table "
                f"{self.name!r}: {sorted(unknown)}"
            )
        self.rows.append(row)


@dataclass(slots=True)
class DgsDocument:
    """Schema-driven DGS tabular document before file serialization."""

    tables: dict[str, DgsTable] = field(default_factory=dict)

    def add_table(self, table: DgsTable) -> None:
        if table.name in self.tables:
            raise ValueError(f"Duplicate DGS table: {table.name}")
        self.tables[table.name] = table

    def get_table(self, name: str) -> DgsTable:
        try:
            return self.tables[name]
        except KeyError as exc:
            raise KeyError(f"Unknown DGS table: {name}") from exc

    def rows(self) -> Iterable[DgsRow]:
        for table in self.tables.values():
            yield from table.rows

    def summary(self) -> dict[str, object]:
        return {
            "tables": len(self.tables),
            "rows": sum(len(table.rows) for table in self.tables.values()),
            "table_rows": {
                name: len(table.rows) for name, table in sorted(self.tables.items())
            },
        }


# Compatibility alias kept for code that imported DgsObject in previous phases.
DgsObject = DgsRow
