from dataclasses import dataclass

from .identifiers import BusId, ElectricalSystemId, FeederId, SubstationId


@dataclass(frozen=True, slots=True)
class Bus:
    id: BusId
    name: str
    nominal_voltage_kv: float
    x: float | None = None
    y: float | None = None
    feeder_id: FeederId | None = None
    system_id: ElectricalSystemId | None = None
    substation_id: SubstationId | None = None

    def __post_init__(self) -> None:
        if not str(self.id).strip():
            raise ValueError("Bus id cannot be empty.")
        if not self.name.strip():
            raise ValueError("Bus name cannot be empty.")
        if self.nominal_voltage_kv <= 0:
            raise ValueError("Bus nominal voltage must be greater than zero.")
