from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from gis2dgs.dgs import (
    DgsClassMapping,
    DgsFormat,
    DgsIdentityMapping,
    DgsReferenceMapping,
    DgsSchema,
    DgsValueMapping,
    UnmappedPolicy,
)

from .loader import load_yaml


class DgsValueMappingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str
    scale: float = 1.0
    offset: float = 0.0
    value_map: dict[str, Any] = Field(default_factory=dict)
    format_string: str | None = None

    def to_domain(self) -> DgsValueMapping:
        return DgsValueMapping(**self.model_dump())


class DgsReferenceMappingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str
    format_string: str = "{target}"

    def to_domain(self) -> DgsReferenceMapping:
        return DgsReferenceMapping(**self.model_dump())


class DgsIdentityMappingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    foreign_key_column: str
    name_column: str
    parent_column: str | None = None

    def to_domain(self) -> DgsIdentityMapping:
        return DgsIdentityMapping(**self.model_dump())


class DgsClassMappingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table: str
    identity: DgsIdentityMappingConfig
    attributes: dict[str, DgsValueMappingConfig] = Field(default_factory=dict)
    references: dict[str, DgsReferenceMappingConfig] = Field(default_factory=dict)
    static_values: dict[str, Any] = Field(default_factory=dict)
    required_columns: list[str] = Field(default_factory=list)
    header_row: int | None = None
    data_start_row: int | None = None

    def to_domain(self) -> DgsClassMapping:
        return DgsClassMapping(
            table=self.table,
            identity=self.identity.to_domain(),
            attributes={name: value.to_domain() for name, value in self.attributes.items()},
            references={
                name: value.to_domain() for name, value in self.references.items()
            },
            static_values=dict(self.static_values),
            required_columns=tuple(self.required_columns),
            header_row=self.header_row,
            data_start_row=self.data_start_row,
        )


class DgsSchemaConfig(BaseModel):
    """Configuration model for a version-neutral DGS schema."""

    model_config = ConfigDict(extra="forbid")

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
    classes: dict[str, DgsClassMappingConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def configured_schema_has_classes(self) -> "DgsSchemaConfig":
        if self.configured and not self.classes:
            raise ValueError("A configured DGS schema must define at least one class mapping.")
        return self

    def to_schema(self, *, base_dir: Path | None = None) -> DgsSchema:
        template = self.template_path
        if template is not None and not template.is_absolute() and base_dir is not None:
            template = (base_dir / template).resolve()
        return DgsSchema(
            configured=self.configured,
            format=self.format,
            dgs_format_version=self.dgs_format_version,
            template_path=template,
            default_header_row=self.default_header_row,
            default_data_start_row=self.default_data_start_row,
            clear_existing_rows=self.clear_existing_rows,
            preserve_unmapped_sheets=self.preserve_unmapped_sheets,
            unmapped_class_policy=self.unmapped_class_policy,
            strict_unmapped_attributes=self.strict_unmapped_attributes,
            strict_unmapped_references=self.strict_unmapped_references,
            allow_create_without_template=self.allow_create_without_template,
            classes={name: value.to_domain() for name, value in self.classes.items()},
        )

    # Compatibility method for v0.8.0 callers.
    def to_profile(self, *, base_dir: Path | None = None) -> DgsSchema:
        return self.to_schema(base_dir=base_dir)


def load_dgs_schema(path: Path) -> DgsSchema:
    config = DgsSchemaConfig.model_validate(load_yaml(path))
    return config.to_schema(base_dir=path.parent)


# Backward-compatibility aliases for v0.8.0 callers.
DgsMappingConfig = DgsSchemaConfig


def load_dgs_mapping_profile(path: Path) -> DgsSchema:
    return load_dgs_schema(path)
