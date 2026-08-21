from dataclasses import dataclass

from .identifiers import BusId, LoadId


@dataclass(frozen=True, slots=True)
class Load:
    id: LoadId
    name: str
    bus_id: BusId
    active_power_mw: float
    reactive_power_mvar: float
    in_service: bool = True

    def __post_init__(self) -> None:
        if not str(self.id).strip():
            raise ValueError("Load id cannot be empty.")
        if self.active_power_mw < 0:
            raise ValueError(f"Load {self.id}: active power cannot be negative.")
