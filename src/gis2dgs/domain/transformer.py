from dataclasses import dataclass

from .identifiers import BusId, TransformerId


@dataclass(frozen=True, slots=True)
class Transformer:
    id: TransformerId
    name: str
    hv_bus: BusId
    lv_bus: BusId
    hv_voltage_kv: float
    lv_voltage_kv: float
    rated_power_mva: float
    type_id: str | None = None
    in_service: bool = True

    def __post_init__(self) -> None:
        if not str(self.id).strip():
            raise ValueError("Transformer id cannot be empty.")
        if self.hv_bus == self.lv_bus:
            raise ValueError(
                f"Transformer {self.id} cannot use the same HV and LV bus."
            )
        if self.hv_voltage_kv <= self.lv_voltage_kv:
            raise ValueError(
                f"Transformer {self.id}: HV voltage must be greater than LV voltage."
            )
        if self.rated_power_mva <= 0:
            raise ValueError(
                f"Transformer {self.id}: rated power must be greater than zero."
            )
