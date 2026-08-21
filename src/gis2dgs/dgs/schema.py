from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from .exceptions import DgsSchemaNotConfiguredError


class DgsFormat(StrEnum):
    """Physical carrier currently implemented for DGS serialization."""

    EXCEL = "excel"


class UnmappedPolicy(StrEnum):
    ERROR = "error"
    SKIP = "skip"


@dataclass(frozen=True, slots=True)
class DgsValueMapping:
    """Map one semantic PowerFactory value to one DGS column.

    ``scale`` and ``offset`` are schema-level transformations. They are useful
    when a DGS reference export represents a semantic quantity with a different
    unit or convention. No PowerFactory/DIgSILENT version number is required.
    ``value_map`` supports enums and booleans, e.g. {"true": 1, "false": 0}.
    """

    column: str
    scale: float = 1.0
    offset: float = 0.0
    value_map: dict[str, Any] = field(default_factory=dict)
    format_string: str | None = None

    def __post_init__(self) -> None:
        if not self.column.strip():
            raise ValueError("DGS target column cannot be empty.")

    def transform(self, value: Any) -> Any:
        if value is None:
            return None

        key = self._mapping_key(value)
        if key in self.value_map:
            value = self.value_map[key]

        if self.format_string is not None:
            return self.format_string.format(value=value)

        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            return value * self.scale + self.offset

        return value

    @staticmethod
    def _mapping_key(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)


@dataclass(frozen=True, slots=True)
class DgsReferenceMapping:
    column: str
    format_string: str = "{target}"

    def __post_init__(self) -> None:
        if not self.column.strip():
            raise ValueError("DGS reference target column cannot be empty.")

    def transform(self, target: str) -> str:
        return self.format_string.format(target=target)


@dataclass(frozen=True, slots=True)
class DgsIdentityMapping:
    foreign_key_column: str
    name_column: str
    parent_column: str | None = None

    def __post_init__(self) -> None:
        if not self.foreign_key_column.strip():
            raise ValueError("DGS foreign-key column cannot be empty.")
        if not self.name_column.strip():
            raise ValueError("DGS name column cannot be empty.")
        if self.parent_column is not None and not self.parent_column.strip():
            raise ValueError("DGS parent column cannot be blank when configured.")


@dataclass(frozen=True, slots=True)
class DgsClassMapping:
    """Schema mapping for one semantic PowerFactory class."""

    table: str
    identity: DgsIdentityMapping
    attributes: dict[str, DgsValueMapping] = field(default_factory=dict)
    references: dict[str, DgsReferenceMapping] = field(default_factory=dict)
    static_values: dict[str, Any] = field(default_factory=dict)
    required_columns: tuple[str, ...] = ()
    header_row: int | None = None
    data_start_row: int | None = None

    def __post_init__(self) -> None:
        if not self.table.strip():
            raise ValueError("DGS table name cannot be empty.")
        if self.header_row is not None and self.header_row < 1:
            raise ValueError("DGS header_row must be >= 1.")
        if self.data_start_row is not None and self.data_start_row < 1:
            raise ValueError("DGS data_start_row must be >= 1.")

    def all_columns(self) -> tuple[str, ...]:
        ordered: list[str] = []

        def add(column: str | None) -> None:
            if column and column not in ordered:
                ordered.append(column)

        add(self.identity.foreign_key_column)
        add(self.identity.name_column)
        add(self.identity.parent_column)
        for mapping in self.attributes.values():
            add(mapping.column)
        for mapping in self.references.values():
            add(mapping.column)
        for column in self.static_values:
            add(column)
        for column in self.required_columns:
            add(column)
        return tuple(ordered)


@dataclass(frozen=True, slots=True)
class DgsSchema:
    """Version-neutral DGS schema and writer policy.

    The schema is driven by the structure observed in a DGS reference export:
    tables/sheets, columns, identity fields, references and transformations.
    Compatibility is therefore checked structurally, not by a DIgSILENT or
    PowerFactory version number.
    """

    configured: bool = False
    format: DgsFormat = DgsFormat.EXCEL
    dgs_format_version: str | None = None
    template_path: Path | None = None
    default_header_row: int = 1
    default_data_start_row: int = 2
    clear_existing_rows: bool = True
    preserve_unmapped_sheets: bool = True
    unmapped_class_policy: UnmappedPolicy = UnmappedPolicy.ERROR
    strict_unmapped_attributes: bool = True
    strict_unmapped_references: bool = True
    allow_create_without_template: bool = False
    classes: dict[str, DgsClassMapping] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.default_header_row < 1:
            raise ValueError("default_header_row must be >= 1.")
        if self.default_data_start_row < 1:
            raise ValueError("default_data_start_row must be >= 1.")

    def require_configured(self) -> None:
        if not self.configured or not self.classes:
            raise DgsSchemaNotConfiguredError(
                "DGS schema is not configured. Inspect a DGS reference export and "
                "configure the required tables, columns and references before serialization."
            )

    def mapping_for(self, class_name: str) -> DgsClassMapping | None:
        return self.classes.get(class_name)


# Backward-compatibility alias for v0.8.0 callers. New code should use DgsSchema.
DgsMappingProfile = DgsSchema
