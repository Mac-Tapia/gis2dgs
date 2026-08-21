from gis2dgs.domain import Bus
from gis2dgs.domain.identifiers import BusId, SubstationId


def test_bus_can_reference_substation() -> None:
    bus = Bus(BusId("B1"), "B1", 10.0, substation_id=SubstationId("S1"))
    assert bus.substation_id == SubstationId("S1")
