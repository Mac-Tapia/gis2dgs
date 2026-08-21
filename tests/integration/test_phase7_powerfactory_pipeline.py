from gis2dgs.domain import Bus, Line, NetworkModel, Source
from gis2dgs.domain.identifiers import BusId, LineId, SourceId
from gis2dgs.electrical import ElectricalLibrary, LineType
from gis2dgs.powerfactory import PowerFactoryMapper, validate_powerfactory_model


def test_network_and_library_map_to_valid_node_breaker_model() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.5, 10.0, "LT"))
    network.add_source(Source(SourceId("GRID"), "Grid", BusId("B1"), 10.0))
    library = ElectricalLibrary.from_types(
        line_types=[LineType("LT", "LT", 10.0, 0.2, 0.1, 200.0)]
    )

    model = PowerFactoryMapper().map(network, library)

    assert validate_powerfactory_model(model).is_valid
    assert len(model.find_by_class("StaCubic")) == 3
    assert len(model.find_by_class("ElmLne")) == 1
    assert len(model.find_by_class("ElmXnet")) == 1
