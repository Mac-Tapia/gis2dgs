from dataclasses import dataclass

from .identifiers import BusId, SourceId


@dataclass(frozen=True, slots=True)
class Source:
    """Grid/source equivalent connected to a bus."""

    id: SourceId
    name: str
    bus_id: BusId
    nominal_voltage_kv: float
    in_service: bool = True

    def __post_init__(self) -> None:
        if not str(self.id).strip():
            raise ValueError("Source id cannot be empty.")
        if not self.name.strip():
            raise ValueError("Source name cannot be empty.")
        if self.nominal_voltage_kv <= 0:
            raise ValueError(f"Source {self.id}: nominal voltage must be greater than zero.")
