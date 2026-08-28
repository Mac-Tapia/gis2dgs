from __future__ import annotations

from dataclasses import dataclass, field

from .classes import PowerFactoryClass


@dataclass(frozen=True, slots=True)
class PowerFactoryGraphicSymbols:
    """PowerFactory netdiag symbol names written to IntGrf.sSymNam."""

    # Point/junction node (not TermStrip busbar) so SLD shows dots, not long bars.
    terminal: str = "Term"
    line: str = "d_lin"
    source: str = "d_sym"
    load: str = "d_load"
    transformer: str = "d_tr2"


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
    # When exact line type_id is missing from the library, assign the nearest
    # library type by voltage or synthesize a TypLne bucket so ElmLne rows keep
    # typ_id(p) — PowerFactory treats lines without typ_id as non-network data.
    fallback_line_types_by_voltage: bool = True
    require_substation_references: bool = False
    include_coordinates: bool = True
    # Projected inventory CRS when coordinate_x/y are UTM-like metres.
    inventory_source_crs: str = "EPSG:32718"
    create_cubicle_switches: bool = False
    create_feeder_graphics: bool = True
    create_feeder_objects: bool = True
    ensure_feeder_sources: bool = True
    prefer_operational_codes: bool = True
    split_networks_by_system: bool = True
    # One IntGrfnet page per feeder even when a single ElmNet is used.
    diagrams_per_feeder: bool = True
    # Skip per-feeder SLD graphics above this size (full BT inventories).
    max_buses_for_feeder_graphics: int = 25_000
    # Max IntGrf axis span after origin shift (diagram units, not GIS metres).
    diagram_target_extent: float = 4000.0
    # auto: GIS when edge lengths stay readable after fit; else topology SLD.
    diagram_layout: str = "auto"
    diagram_min_edge_length: float = 20.0
    # ElmTerm.iUsage: 0=busbar, 1=junction node, 2=internal.
    terminal_usage: int = 1
    graphic_symbols: PowerFactoryGraphicSymbols = field(
        default_factory=PowerFactoryGraphicSymbols
    )
    classes: PowerFactoryClassMap = field(default_factory=PowerFactoryClassMap)

    def __post_init__(self) -> None:
        if not self.network_id.strip():
            raise ValueError("PowerFactory network_id cannot be empty.")
        if not self.network_name.strip():
            raise ValueError("PowerFactory network_name cannot be empty.")
        if not self.foreign_key_prefix.strip():
            raise ValueError("PowerFactory foreign_key_prefix cannot be empty.")
        layout = self.diagram_layout.strip().lower()
        if layout not in {"auto", "gis", "topology"}:
            raise ValueError(
                "diagram_layout must be one of: auto, gis, topology."
            )
        object.__setattr__(self, "diagram_layout", layout)
        if self.diagram_target_extent <= 0:
            raise ValueError("diagram_target_extent must be positive.")
        if self.diagram_min_edge_length < 0:
            raise ValueError("diagram_min_edge_length cannot be negative.")
        if self.terminal_usage not in {0, 1, 2}:
            raise ValueError(
                "terminal_usage must be 0 (busbar), 1 (junction), or 2 (internal)."
            )
