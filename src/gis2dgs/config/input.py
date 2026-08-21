from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .loader import load_yaml


class InputSourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    uri: str
    kind: Literal[
        "auto",
        "excel",
        "csv",
        "vector",
        "parquet",
        "database",
        "mssql_backup",
        "cymdist_text",
    ] = "auto"
    options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", "uri")
    @classmethod
    def non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Input source id/uri cannot be blank.")
        return value

    def resolved_uri(self, base_dir: Path) -> str:
        expanded = os.path.expandvars(self.uri)
        if "://" in expanded:
            return expanded
        path = Path(expanded)
        if not path.is_absolute():
            path = (base_dir / path).resolve()
        return str(path)


class InputManifestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[InputSourceConfig]
    on_conflict: str = "error"

    @field_validator("sources")
    @classmethod
    def require_sources(cls, value: list[InputSourceConfig]) -> list[InputSourceConfig]:
        if not value:
            raise ValueError("At least one input source is required.")
        ids = [source.id for source in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Input source ids must be unique.")
        return value

    @field_validator("on_conflict")
    @classmethod
    def valid_conflict_policy(cls, value: str) -> str:
        if value not in {"error", "overwrite"}:
            raise ValueError("on_conflict must be 'error' or 'overwrite'.")
        return value


def load_input_manifest(path: Path) -> InputManifestConfig:
    return InputManifestConfig.model_validate(load_yaml(path))
