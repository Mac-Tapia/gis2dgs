from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

UnitCode = Literal[
    "V",
    "kV",
    "m",
    "km",
    "W",
    "kW",
    "MW",
    "var",
    "kvar",
    "Mvar",
    "VA",
    "kVA",
    "MVA",
]


class LayerMapping(BaseModel):
    """Configuration for mapping one GIS layer to one domain entity type."""

    model_config = ConfigDict(extra="forbid")

    source: str
    fields: dict[str, str] = Field(default_factory=dict)
    units: dict[str, UnitCode] = Field(default_factory=dict)
    defaults: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source")
    @classmethod
    def source_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Layer source cannot be empty.")
        return value

    @field_validator("fields")
    @classmethod
    def field_names_must_not_be_blank(cls, value: dict[str, str]) -> dict[str, str]:
        cleaned: dict[str, str] = {}
        for logical_name, source_name in value.items():
            logical = logical_name.strip()
            source = source_name.strip()
            if not logical or not source:
                raise ValueError("Mapping field names cannot be empty.")
            cleaned[logical] = source
        return cleaned


class ConnectivityConfig(BaseModel):
    """Spatial endpoint reconstruction: propose first, then apply unambiguous links."""

    model_config = ConfigDict(extra="forbid")

    apply_unambiguous: bool = True
    tolerance_m: float = 2.0
    tie_tolerance_m: float = 1e-6


class MappingConfig(BaseModel):
    """Phase 3 GIS → canonical electrical model mapping configuration."""

    model_config = ConfigDict(extra="forbid")

    target_crs: str | None = None
    connectivity: ConnectivityConfig = Field(default_factory=ConnectivityConfig)
    buses: LayerMapping | None = None
    lines: LayerMapping | None = None
    transformers: LayerMapping | None = None
    switches: LayerMapping | None = None
    loads: LayerMapping | None = None
    generators: LayerMapping | None = None
    sources: LayerMapping | None = None
    substations: LayerMapping | None = None


def load_mapping_config(path):
    from pathlib import Path

    from .loader import load_yaml

    return MappingConfig.model_validate(load_yaml(Path(path)))
