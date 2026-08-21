from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator

from .input import InputManifestConfig
from .loader import load_yaml


class ProjectConfig(BaseModel):
    """End-to-end, reproducible conversion project configuration."""

    model_config = ConfigDict(extra="forbid")

    name: str = "gis2dgs-project"
    inputs: InputManifestConfig
    mapping: Path
    validation: Path
    electrical_library: Path
    powerfactory_mapping: Path
    dgs_schema: Path
    output_dgs: Path
    validation_json: Path = Path("output/validation/report.json")
    validation_csv: Path = Path("output/validation/report.csv")
    schema_report: Path = Path("output/validation/input_schema.yaml")
    fail_on_validation_errors: bool = True

    @field_validator("name")
    @classmethod
    def non_blank_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name cannot be blank.")
        return value

    def resolve(self, base_dir: Path) -> "ResolvedProjectConfig":
        def path(value: Path) -> Path:
            return value if value.is_absolute() else (base_dir / value).resolve()

        return ResolvedProjectConfig(
            name=self.name,
            inputs=self.inputs,
            base_dir=base_dir,
            mapping=path(self.mapping),
            validation=path(self.validation),
            electrical_library=path(self.electrical_library),
            powerfactory_mapping=path(self.powerfactory_mapping),
            dgs_schema=path(self.dgs_schema),
            output_dgs=path(self.output_dgs),
            validation_json=path(self.validation_json),
            validation_csv=path(self.validation_csv),
            schema_report=path(self.schema_report),
            fail_on_validation_errors=self.fail_on_validation_errors,
        )


class ResolvedProjectConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    inputs: InputManifestConfig
    base_dir: Path
    mapping: Path
    validation: Path
    electrical_library: Path
    powerfactory_mapping: Path
    dgs_schema: Path
    output_dgs: Path
    validation_json: Path
    validation_csv: Path
    schema_report: Path
    fail_on_validation_errors: bool


def load_project_config(path: Path) -> ResolvedProjectConfig:
    raw = ProjectConfig.model_validate(load_yaml(path))
    return raw.resolve(path.parent.resolve())
