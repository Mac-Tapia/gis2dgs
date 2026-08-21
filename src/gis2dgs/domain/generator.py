from dataclasses import dataclass

from .identifiers import BusId, GeneratorId


@dataclass(frozen=True, slots=True)
class Generator:
    """Canonical distributed or embedded generation connected to a bus.

    Positive active power represents generation injected into the network.
    Reactive power may be positive or negative depending on the operating point.
    """

    id: GeneratorId
    name: str
    bus_id: BusId
    active_power_mw: float
    reactive_power_mvar: float = 0.0
    technology: str | None = None
    in_service: bool = True

    def __post_init__(self) -> None:
        if not str(self.id).strip():
            raise ValueError("Generator id cannot be empty.")
        if not self.name.strip():
            raise ValueError("Generator name cannot be empty.")
        if self.active_power_mw < 0:
            raise ValueError(
                f"Generator {self.id}: active power cannot be negative."
            )
        if self.technology is not None and not self.technology.strip():
            raise ValueError(
                f"Generator {self.id}: technology cannot be blank when provided."
            )
