from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from gis2dgs.electrical import ElectricalLibrary, LineType, TransformerType

from .loader import load_yaml


class LineTypeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    nominal_voltage_kv: float
    r1_ohm_per_km: float
    x1_ohm_per_km: float
    rated_current_a: float
    c1_nf_per_km: float = 0.0
    r0_ohm_per_km: float | None = None
    x0_ohm_per_km: float | None = None
    c0_nf_per_km: float | None = None
    phases: int = 3

    @field_validator("name")
    @classmethod
    def non_blank_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Line type name cannot be empty.")
        return value

    def to_domain(self, type_id: str) -> LineType:
        return LineType(id=type_id, **self.model_dump())


class TransformerTypeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    rated_power_mva: float
    hv_voltage_kv: float
    lv_voltage_kv: float
    uk_percent: float
    copper_loss_kw: float
    no_load_loss_kw: float
    no_load_current_percent: float
    vector_group: str
    phase_shift_deg: float = 0.0
    uk0_percent: float | None = None
    ur0_percent: float | None = None

    @field_validator("name", "vector_group")
    @classmethod
    def non_blank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Transformer type text fields cannot be empty.")
        return value

    def to_domain(self, type_id: str) -> TransformerType:
        return TransformerType(id=type_id, **self.model_dump())


class ElectricalLibraryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_types: dict[str, LineTypeConfig] = Field(default_factory=dict)
    transformer_types: dict[str, TransformerTypeConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def identifiers_must_not_be_blank(self) -> "ElectricalLibraryConfig":
        for collection_name, collection in (
            ("line_types", self.line_types),
            ("transformer_types", self.transformer_types),
        ):
            for type_id in collection:
                if not type_id.strip():
                    raise ValueError(f"{collection_name} contains an empty type identifier.")
        return self

    def to_domain(self) -> ElectricalLibrary:
        return ElectricalLibrary.from_types(
            line_types=(
                config.to_domain(type_id)
                for type_id, config in self.line_types.items()
            ),
            transformer_types=(
                config.to_domain(type_id)
                for type_id, config in self.transformer_types.items()
            ),
        )


def parse_electrical_library(data: dict[str, Any]) -> ElectricalLibrary:
    return ElectricalLibraryConfig.model_validate(data).to_domain()


def load_electrical_library(path: Path) -> ElectricalLibrary:
    return parse_electrical_library(load_yaml(path))
