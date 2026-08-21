import pytest

from gis2dgs.domain.identifiers import BusId, LineId
from gis2dgs.domain.line import Line


def test_line_rejects_same_terminal() -> None:
    with pytest.raises(ValueError):
        Line(
            id=LineId("L1"),
            name="L1",
            from_bus=BusId("B1"),
            to_bus=BusId("B1"),
            length_km=1.0,
            nominal_voltage_kv=10.0,
        )
