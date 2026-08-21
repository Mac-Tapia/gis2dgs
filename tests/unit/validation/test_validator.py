from gis2dgs.domain import Bus, BusId, Line, LineId, NetworkModel, Source, SourceId
from gis2dgs.validation import NetworkValidator


def test_valid_energized_network() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0))
    network.add_source(Source(SourceId("SRC1"), "Grid", BusId("B1"), 10.0))
    report = NetworkValidator().validate(network)
    assert report.is_valid
    assert report.warnings == []
