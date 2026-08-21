from gis2dgs.domain import Bus, BusId, Line, LineId, Load, LoadId, NetworkModel, Source, SourceId
from gis2dgs.topology import build_graph, trace_from
from gis2dgs.validation import NetworkValidator


def test_domain_topology_validation_pipeline() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "SET", 10.0))
    network.add_bus(Bus(BusId("B2"), "LOAD BUS", 10.0))
    network.add_line(Line(LineId("L1"), "FEEDER", BusId("B1"), BusId("B2"), 1.2, 10.0))
    network.add_source(Source(SourceId("SRC1"), "External Grid", BusId("B1"), 10.0))
    network.add_load(Load(LoadId("LD1"), "Customer", BusId("B2"), 0.5, 0.1))

    graph = build_graph(network)
    assert trace_from(graph, "B1") == {"B1", "B2"}
    assert NetworkValidator().validate(network).is_valid
