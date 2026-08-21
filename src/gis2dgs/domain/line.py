from dataclasses import dataclass

from .identifiers import BusId, LineId


@dataclass(frozen=True, slots=True)
class Line:
    id: LineId
    name: str
    from_bus: BusId
    to_bus: BusId
    length_km: float
    nominal_voltage_kv: float
    type_id: str | None = None
    in_service: bool = True

    def __post_init__(self) -> None:
        if not str(self.id).strip():
            raise ValueError("Line id cannot be empty.")
        if self.from_bus == self.to_bus:
            raise ValueError(f"Line {self.id} cannot connect a bus to itself.")
        if self.length_km <= 0:
            raise ValueError(f"Line {self.id} must have a positive length.")
        if self.nominal_voltage_kv <= 0:
            raise ValueError(f"Line {self.id} must have a positive voltage.")
