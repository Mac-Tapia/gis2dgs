from gis2dgs.domain import Bus, BusId, Line, LineId, NetworkModel, Source, SourceId
from gis2dgs.electrical import ElectricalLibrary, LineType
from gis2dgs.validation import NetworkValidator, ValidationPolicy


def test_phase5_pipeline_still_valid_with_phase6_library_resolution() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_source(Source(SourceId("GRID"), "Grid", BusId("B1"), 10.0))
    network.add_line(
        Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0, "LT1")
    )
    library = ElectricalLibrary.from_types(
        line_types=[LineType("LT1", "Synthetic line", 10.0, 0.4, 0.3, 200.0)]
    )
    report = NetworkValidator(
        ValidationPolicy.power_flow(), electrical_library=library
    ).validate(network)
    assert report.is_valid
