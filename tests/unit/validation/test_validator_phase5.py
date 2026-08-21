from gis2dgs.domain import Bus, BusId, Line, LineId, NetworkModel, Source, SourceId
from gis2dgs.electrical import ElectricalLibrary, LineType
from gis2dgs.validation import NetworkValidator, ValidationPolicy


def _typed_network() -> NetworkModel:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_source(Source(SourceId("GRID"), "Grid", BusId("B1"), 10.0))
    network.add_line(
        Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0, "LT1")
    )
    return network


def _library() -> ElectricalLibrary:
    return ElectricalLibrary.from_types(
        line_types=[LineType("LT1", "Synthetic line", 10.0, 0.4, 0.3, 200.0)]
    )


def test_standard_validator_accepts_typed_network_without_library() -> None:
    report = NetworkValidator().validate(_typed_network())
    assert report.is_valid


def test_power_flow_profile_accepts_typed_energized_line_network() -> None:
    report = NetworkValidator(
        ValidationPolicy.power_flow(), electrical_library=_library()
    ).validate(_typed_network())
    assert report.profile == "power_flow"
    assert report.is_valid


def test_standard_validator_reports_unreachable_bus_as_warning() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    report = NetworkValidator().validate(network)
    assert report.warning_count >= 1
