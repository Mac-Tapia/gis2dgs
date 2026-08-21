from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Literal

Sequence = Literal[0, 1]
TransformerSide = Literal["hv", "lv"]


def _require_finite(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite.")


def _require_positive(name: str, value: float) -> None:
    _require_finite(name, value)
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")


def _require_non_negative(name: str, value: float) -> None:
    _require_finite(name, value)
    if value < 0:
        raise ValueError(f"{name} cannot be negative.")


@dataclass(frozen=True, slots=True)
class LineType:
    """Canonical line/cable type independent from PowerFactory field names.

    Impedances and capacitances are positive/zero-sequence values per kilometre.
    The DGS-specific mapping is intentionally deferred to Phase 7/8.
    """

    id: str
    name: str
    nominal_voltage_kv: float
    r1_ohm_per_km: float
    x1_ohm_per_km: float
    rated_current_a: float
    c1_nf_per_km: float = 0.0
    r0_ohm_per_km: float | None = None
    x0_ohm_per_km: float | None = None
    c0_nf_per_km: float | None = None
    phases: int = 3

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Line type id cannot be empty.")
        if not self.name.strip():
            raise ValueError("Line type name cannot be empty.")
        _require_positive("nominal_voltage_kv", self.nominal_voltage_kv)
        _require_positive("r1_ohm_per_km", self.r1_ohm_per_km)
        _require_non_negative("x1_ohm_per_km", self.x1_ohm_per_km)
        _require_positive("rated_current_a", self.rated_current_a)
        _require_non_negative("c1_nf_per_km", self.c1_nf_per_km)
        if self.phases not in {1, 2, 3}:
            raise ValueError("Line type phases must be 1, 2, or 3.")

        zero_values = (self.r0_ohm_per_km, self.x0_ohm_per_km, self.c0_nf_per_km)
        if any(value is not None for value in zero_values) and not all(
            value is not None for value in zero_values
        ):
            raise ValueError(
                "Zero-sequence line data must provide r0, x0, and c0 together."
            )
        if self.r0_ohm_per_km is not None:
            _require_positive("r0_ohm_per_km", self.r0_ohm_per_km)
            _require_non_negative("x0_ohm_per_km", self.x0_ohm_per_km or 0.0)
            _require_non_negative("c0_nf_per_km", self.c0_nf_per_km or 0.0)

    @property
    def has_zero_sequence_data(self) -> bool:
        return self.r0_ohm_per_km is not None

    def series_impedance_ohm(self, length_km: float, sequence: Sequence = 1) -> complex:
        _require_positive("length_km", length_km)
        if sequence not in {0, 1}:
            raise ValueError("sequence must be 0 or 1.")
        if sequence == 1:
            return complex(
                self.r1_ohm_per_km * length_km,
                self.x1_ohm_per_km * length_km,
            )
        if not self.has_zero_sequence_data:
            raise ValueError(f"Line type {self.id} has no zero-sequence data.")
        assert self.r0_ohm_per_km is not None
        assert self.x0_ohm_per_km is not None
        return complex(
            self.r0_ohm_per_km * length_km,
            self.x0_ohm_per_km * length_km,
        )

    def shunt_capacitance_nf(self, length_km: float, sequence: Sequence = 1) -> float:
        _require_positive("length_km", length_km)
        if sequence not in {0, 1}:
            raise ValueError("sequence must be 0 or 1.")
        if sequence == 1:
            return self.c1_nf_per_km * length_km
        if not self.has_zero_sequence_data:
            raise ValueError(f"Line type {self.id} has no zero-sequence data.")
        assert self.c0_nf_per_km is not None
        return self.c0_nf_per_km * length_km


@dataclass(frozen=True, slots=True)
class TransformerType:
    """Canonical two-winding transformer type for electrical studies."""

    id: str
    name: str
    rated_power_mva: float
    hv_voltage_kv: float
    lv_voltage_kv: float
    uk_percent: float
    copper_loss_kw: float
    no_load_loss_kw: float
    no_load_current_percent: float
    vector_group: str
    phase_shift_deg: float = 0.0
    uk0_percent: float | None = None
    ur0_percent: float | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Transformer type id cannot be empty.")
        if not self.name.strip():
            raise ValueError("Transformer type name cannot be empty.")
        if not self.vector_group.strip():
            raise ValueError("Transformer vector group cannot be empty.")
        _require_positive("rated_power_mva", self.rated_power_mva)
        _require_positive("hv_voltage_kv", self.hv_voltage_kv)
        _require_positive("lv_voltage_kv", self.lv_voltage_kv)
        if self.hv_voltage_kv <= self.lv_voltage_kv:
            raise ValueError("Transformer type HV voltage must be greater than LV voltage.")
        _require_positive("uk_percent", self.uk_percent)
        if self.uk_percent > 100:
            raise ValueError("Transformer uk_percent cannot exceed 100%.")
        _require_non_negative("copper_loss_kw", self.copper_loss_kw)
        _require_non_negative("no_load_loss_kw", self.no_load_loss_kw)
        _require_non_negative("no_load_current_percent", self.no_load_current_percent)
        _require_finite("phase_shift_deg", self.phase_shift_deg)

        if (self.uk0_percent is None) != (self.ur0_percent is None):
            raise ValueError("Transformer zero-sequence data must provide uk0 and ur0 together.")
        if self.uk0_percent is not None:
            _require_positive("uk0_percent", self.uk0_percent)
            _require_non_negative("ur0_percent", self.ur0_percent or 0.0)
            if (self.ur0_percent or 0.0) > self.uk0_percent:
                raise ValueError("Transformer ur0_percent cannot exceed uk0_percent.")

        if self.short_circuit_r_percent > self.uk_percent + 1e-12:
            raise ValueError(
                "Transformer copper loss implies a resistive short-circuit component "
                "greater than uk_percent."
            )

    @property
    def has_zero_sequence_data(self) -> bool:
        return self.uk0_percent is not None

    @property
    def short_circuit_r_percent(self) -> float:
        return self.copper_loss_kw / (self.rated_power_mva * 1000.0) * 100.0

    @property
    def short_circuit_x_percent(self) -> float:
        r_percent = self.short_circuit_r_percent
        return sqrt(max(self.uk_percent**2 - r_percent**2, 0.0))

    def base_impedance_ohm(self, side: TransformerSide = "hv") -> float:
        if side not in {"hv", "lv"}:
            raise ValueError("side must be 'hv' or 'lv'.")
        voltage_kv = self.hv_voltage_kv if side == "hv" else self.lv_voltage_kv
        return voltage_kv**2 / self.rated_power_mva

    def short_circuit_impedance_ohm(self, side: TransformerSide = "hv") -> complex:
        z_base = self.base_impedance_ohm(side)
        return complex(
            z_base * self.short_circuit_r_percent / 100.0,
            z_base * self.short_circuit_x_percent / 100.0,
        )
