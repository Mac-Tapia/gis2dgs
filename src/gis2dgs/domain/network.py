from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .bus import Bus
from .identifiers import (
    BusId,
    GeneratorId,
    LineId,
    LoadId,
    SourceId,
    SubstationId,
    SwitchId,
    TransformerId,
)
from .generator import Generator
from .line import Line
from .load import Load
from .source import Source
from .substation import Substation
from .switch import Switch
from .transformer import Transformer


@dataclass(slots=True)
class NetworkModel:
    buses: dict[BusId, Bus] = field(default_factory=dict)
    lines: dict[LineId, Line] = field(default_factory=dict)
    transformers: dict[TransformerId, Transformer] = field(default_factory=dict)
    switches: dict[SwitchId, Switch] = field(default_factory=dict)
    loads: dict[LoadId, Load] = field(default_factory=dict)
    generators: dict[GeneratorId, Generator] = field(default_factory=dict)
    sources: dict[SourceId, Source] = field(default_factory=dict)
    substations: dict[SubstationId, Substation] = field(default_factory=dict)

    def add_bus(self, bus: Bus) -> None:
        self._reject_duplicate(bus.id, self.buses, "bus")
        self.buses[bus.id] = bus

    def add_line(self, line: Line) -> None:
        self._reject_duplicate(line.id, self.lines, "line")
        self.lines[line.id] = line

    def add_transformer(self, transformer: Transformer) -> None:
        self._reject_duplicate(transformer.id, self.transformers, "transformer")
        self.transformers[transformer.id] = transformer

    def add_switch(self, switch: Switch) -> None:
        self._reject_duplicate(switch.id, self.switches, "switch")
        self.switches[switch.id] = switch

    def add_load(self, load: Load) -> None:
        self._reject_duplicate(load.id, self.loads, "load")
        self.loads[load.id] = load

    def add_generator(self, generator: Generator) -> None:
        self._reject_duplicate(generator.id, self.generators, "generator")
        self.generators[generator.id] = generator

    def add_source(self, source: Source) -> None:
        self._reject_duplicate(source.id, self.sources, "source")
        self.sources[source.id] = source

    def add_substation(self, substation: Substation) -> None:
        self._reject_duplicate(substation.id, self.substations, "substation")
        self.substations[substation.id] = substation

    def has_bus(self, bus_id: BusId) -> bool:
        return bus_id in self.buses

    def summary(self) -> dict[str, int]:
        return {
            "buses": len(self.buses),
            "lines": len(self.lines),
            "transformers": len(self.transformers),
            "switches": len(self.switches),
            "loads": len(self.loads),
            "generators": len(self.generators),
            "sources": len(self.sources),
            "substations": len(self.substations),
        }

    @staticmethod
    def _reject_duplicate(
        object_id: object,
        collection: Mapping[Any, Any],
        object_name: str,
    ) -> None:
        if object_id in collection:
            raise ValueError(f"Duplicate {object_name} ID: {object_id}")
