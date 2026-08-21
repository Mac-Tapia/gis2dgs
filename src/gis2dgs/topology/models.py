from dataclasses import dataclass
from enum import StrEnum


class CycleKind(StrEnum):
    SIMPLE = "simple"
    PARALLEL = "parallel"


@dataclass(frozen=True, slots=True, order=True)
class EdgeRef:
    object_type: str
    object_id: str
    key: str


@dataclass(frozen=True, slots=True)
class TopologyIsland:
    island_id: str
    buses: frozenset[str]
    source_ids: tuple[str, ...]
    edge_count: int
    energized: bool
    radial: bool

    @property
    def bus_count(self) -> int:
        return len(self.buses)


@dataclass(frozen=True, slots=True)
class SourceTrace:
    source_id: str
    source_bus: str
    buses: frozenset[str]
    edges: tuple[EdgeRef, ...]


@dataclass(frozen=True, slots=True)
class FeederTrace:
    feeder_id: str
    source_id: str
    source_bus: str
    root_bus: str
    root_edge: EdgeRef
    label: str | None
    buses: frozenset[str]
    edges: tuple[EdgeRef, ...]
    boundary_buses: frozenset[str]
    has_cycle: bool


@dataclass(frozen=True, slots=True)
class BranchTrace:
    branch_id: str
    start_bus: str
    end_bus: str
    buses: tuple[str, ...]
    edges: tuple[EdgeRef, ...]
    has_cycle: bool = False


@dataclass(frozen=True, slots=True)
class CycleTrace:
    cycle_id: str
    kind: CycleKind
    buses: tuple[str, ...]
    edges: tuple[EdgeRef, ...]


@dataclass(frozen=True, slots=True)
class OpenSwitchBoundary:
    switch_id: str
    from_bus: str
    to_bus: str
    from_energized: bool
    to_energized: bool

    @property
    def separates_energized_from_deenergized(self) -> bool:
        return self.from_energized != self.to_energized


@dataclass(frozen=True, slots=True)
class FeederOverlap:
    bus_id: str
    feeder_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TopologyReport:
    islands: tuple[TopologyIsland, ...]
    source_traces: tuple[SourceTrace, ...]
    feeders: tuple[FeederTrace, ...]
    branches: tuple[BranchTrace, ...]
    cycles: tuple[CycleTrace, ...]
    open_switch_boundaries: tuple[OpenSwitchBoundary, ...]
    feeder_overlaps: tuple[FeederOverlap, ...]
    energized_buses: frozenset[str]
    deenergized_buses: frozenset[str]

    @property
    def is_radial(self) -> bool:
        energized_islands = [island for island in self.islands if island.energized]
        return bool(energized_islands) and all(island.radial for island in energized_islands)
