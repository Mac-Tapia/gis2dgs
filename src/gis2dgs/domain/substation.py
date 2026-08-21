from dataclasses import dataclass

from .identifiers import SubstationId


@dataclass(frozen=True, slots=True)
class Substation:
    id: SubstationId
    name: str
    x: float | None = None
    y: float | None = None

    def __post_init__(self) -> None:
        if not str(self.id).strip():
            raise ValueError("Substation id cannot be empty.")
        if not self.name.strip():
            raise ValueError("Substation name cannot be empty.")
