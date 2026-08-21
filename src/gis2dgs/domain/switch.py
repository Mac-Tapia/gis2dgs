from dataclasses import dataclass

from .identifiers import BusId, SwitchId


@dataclass(frozen=True, slots=True)
class Switch:
    id: SwitchId
    name: str
    from_bus: BusId
    to_bus: BusId
    closed: bool = True
    in_service: bool = True

    def __post_init__(self) -> None:
        if not str(self.id).strip():
            raise ValueError("Switch id cannot be empty.")
        if self.from_bus == self.to_bus:
            raise ValueError(f"Switch {self.id} cannot connect a bus to itself.")
