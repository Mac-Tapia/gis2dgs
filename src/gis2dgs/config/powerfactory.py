from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gis2dgs.powerfactory import PowerFactoryClassMap, PowerFactoryMappingPolicy
from gis2dgs.powerfactory.policy import PowerFactoryGraphicSymbols

from .loader import load_yaml


class PowerFactoryClassMapConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    network: str = "ElmNet"
    substation: str = "ElmSubstat"
    terminal: str = "ElmTerm"
    cubicle: str = "StaCubic"
    cubicle_switch: str = "StaSwitch"
    line: str = "ElmLne"
    line_type: str = "TypLne"
    transformer: str = "ElmTr2"
    transformer_type: str = "TypTr2"
    switch: str = "ElmCoup"
    load: str = "ElmLod"
    generator: str = "ElmGenstat"
    source: str = "ElmXnet"
    feeder: str = "ElmFeeder"
    graphic_net: str = "IntGrfnet"
    graphic: str = "IntGrf"
    graphic_con: str = "IntGrfcon"


class PowerFactoryGraphicSymbolsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    terminal: str = "Term"
    line: str = "d_lin"
    source: str = "d_sym"
    load: str = "d_load"
    transformer: str = "d_tr2"


class PowerFactoryMappingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    network_id: str = "NETWORK"
    network_name: str = "GIS2DGS Network"
    foreign_key_prefix: str = "GIS2DGS"
    include_out_of_service: bool = True
    require_type_references: bool = True
    fallback_line_types_by_voltage: bool = True
    require_substation_references: bool = False
    include_coordinates: bool = True
    create_cubicle_switches: bool = False
    create_feeder_graphics: bool = True
    create_feeder_objects: bool = True
    ensure_feeder_sources: bool = True
    prefer_operational_codes: bool = True
    split_networks_by_system: bool = True
    diagrams_per_feeder: bool = True
    max_buses_for_feeder_graphics: int = 25_000
    diagram_target_extent: float = 4000.0
    diagram_layout: str = "auto"
    diagram_min_edge_length: float = 20.0
    terminal_usage: int = 1
    graphic_symbols: PowerFactoryGraphicSymbolsConfig = Field(
        default_factory=PowerFactoryGraphicSymbolsConfig
    )
    classes: PowerFactoryClassMapConfig = PowerFactoryClassMapConfig()

    def to_policy(self) -> PowerFactoryMappingPolicy:
        return PowerFactoryMappingPolicy(
            network_id=self.network_id,
            network_name=self.network_name,
            foreign_key_prefix=self.foreign_key_prefix,
            include_out_of_service=self.include_out_of_service,
            require_type_references=self.require_type_references,
            fallback_line_types_by_voltage=self.fallback_line_types_by_voltage,
            require_substation_references=self.require_substation_references,
            include_coordinates=self.include_coordinates,
            create_cubicle_switches=self.create_cubicle_switches,
            create_feeder_graphics=self.create_feeder_graphics,
            create_feeder_objects=self.create_feeder_objects,
            ensure_feeder_sources=self.ensure_feeder_sources,
            prefer_operational_codes=self.prefer_operational_codes,
            split_networks_by_system=self.split_networks_by_system,
            diagrams_per_feeder=self.diagrams_per_feeder,
            max_buses_for_feeder_graphics=self.max_buses_for_feeder_graphics,
            diagram_target_extent=self.diagram_target_extent,
            diagram_layout=self.diagram_layout,
            diagram_min_edge_length=self.diagram_min_edge_length,
            terminal_usage=self.terminal_usage,
            graphic_symbols=PowerFactoryGraphicSymbols(
                **self.graphic_symbols.model_dump()
            ),
            classes=PowerFactoryClassMap(**self.classes.model_dump()),
        )


def load_powerfactory_mapping_policy(path: Path) -> PowerFactoryMappingPolicy:
    return PowerFactoryMappingConfig.model_validate(load_yaml(path)).to_policy()
