from __future__ import annotations

from dataclasses import dataclass, field

from .classes import PowerFactoryClass


@dataclass(frozen=True, slots=True)
class PowerFactoryClassMap:
    network: str = PowerFactoryClass.NETWORK
    substation: str = PowerFactoryClass.SUBSTATION
    terminal: str = PowerFactoryClass.TERMINAL
    cubicle: str = PowerFactoryClass.CUBICLE
    cubicle_switch: str = PowerFactoryClass.CUBICLE_SWITCH
    line: str = PowerFactoryClass.LINE
    line_type: str = PowerFactoryClass.LINE_TYPE
    transformer: str = PowerFactoryClass.TRANSFORMER
    transformer_type: str = PowerFactoryClass.TRANSFORMER_TYPE
    switch: str = PowerFactoryClass.SWITCH
    load: str = PowerFactoryClass.LOAD
    generator: str = PowerFactoryClass.GENERATOR
    source: str = PowerFactoryClass.EXTERNAL_GRID
    feeder: str = PowerFactoryClass.FEEDER
    graphic_net: str = PowerFactoryClass.GRAPHIC_NET
    graphic: str = PowerFactoryClass.GRAPHIC
    graphic_con: str = PowerFactoryClass.GRAPHIC_CON


@dataclass(frozen=True, slots=True)
class PowerFactoryMappingPolicy:
    """Configuration for Phase 7 canonical PowerFactory mapping."""

    network_id: str = "NETWORK"
    network_name: str = "GIS2DGS Network"
    foreign_key_prefix: str = "GIS2DGS"
    include_out_of_service: bool = True
    require_type_references: bool = True
    require_substation_references: bool = False
    include_coordinates: bool = True
    create_cubicle_switches: bool = False
    create_feeder_graphics: bool = True
    create_feeder_objects: bool = True
    ensure_feeder_sources: bool = True
    prefer_operational_codes: bool = True
    split_networks_by_system: bool = True
    # Skip per-feeder SLD graphics above this size (full BT inventories).
    max_buses_for_feeder_graphics: int = 25_000
    classes: PowerFactoryClassMap = field(default_factory=PowerFactoryClassMap)

    def __post_init__(self) -> None:
        if not self.network_id.strip():
            raise ValueError("PowerFactory network_id cannot be empty.")
        if not self.network_name.strip():
            raise ValueError("PowerFactory network_name cannot be empty.")
        if not self.foreign_key_prefix.strip():
            raise ValueError("PowerFactory foreign_key_prefix cannot be empty.")
