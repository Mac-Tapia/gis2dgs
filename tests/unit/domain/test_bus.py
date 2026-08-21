import pytest

from gis2dgs.domain.bus import Bus
from gis2dgs.domain.identifiers import BusId


def test_bus_accepts_valid_values() -> None:
    bus = Bus(BusId("BUS_001"), "Barra 10 kV", 10.0)
    assert bus.nominal_voltage_kv == 10.0


def test_bus_rejects_zero_voltage() -> None:
    with pytest.raises(ValueError):
        Bus(BusId("BUS_001"), "Barra", 0.0)
