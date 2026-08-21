from gis2dgs.domain import (
    Bus,
    BusId,
    FeederId,
    Line,
    LineId,
    NetworkModel,
    Source,
    SourceId,
    Switch,
    SwitchId,
    Transformer,
    TransformerId,
)
from gis2dgs.topology import (
    TracePolicy,
    energized_buses,
    find_feeder_overlaps,
    find_open_switch_boundaries,
    trace_feeders,
)


def test_feeder_trace_stops_at_transformer_by_default() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B0"), "B0", 10.0))
    network.add_bus(Bus(BusId("B1"), "B1", 10.0, feeder_id=FeederId("F01")))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_bus(Bus(BusId("B3"), "B3", 0.4))
    network.add_source(Source(SourceId("SRC"), "Grid", BusId("B0"), 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B0"), BusId("B1"), 0.1, 10.0))
    network.add_line(Line(LineId("L2"), "L2", BusId("B1"), BusId("B2"), 0.1, 10.0))
    network.add_transformer(
        Transformer(
            TransformerId("TR1"),
            "TR1",
            BusId("B2"),
            BusId("B3"),
            10.0,
            0.4,
            0.63,
        )
    )

    feeders = trace_feeders(network)

    assert len(feeders) == 1
    assert feeders[0].label == "F01"
    assert feeders[0].buses == frozenset({"B0", "B1", "B2"})
    assert "B2" in feeders[0].boundary_buses
    assert {edge.object_id for edge in feeders[0].edges} == {"L1", "L2"}


def test_feeder_trace_can_cross_transformer_when_policy_allows_it() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B0"), "B0", 10.0))
    network.add_bus(Bus(BusId("B1"), "B1", 0.4))
    network.add_source(Source(SourceId("SRC"), "Grid", BusId("B0"), 10.0))
    network.add_transformer(
        Transformer(
            TransformerId("TR1"),
            "TR1",
            BusId("B0"),
            BusId("B1"),
            10.0,
            0.4,
            0.63,
        )
    )

    feeders = trace_feeders(network, policy=TracePolicy(cross_transformers=True))

    assert len(feeders) == 1
    assert feeders[0].buses == frozenset({"B0", "B1"})
    assert feeders[0].root_edge.object_type == "transformer"


def test_open_switch_boundary_reports_energized_side() -> None:
    network = NetworkModel()
    for bus_id in ("B1", "B2", "B3"):
        network.add_bus(Bus(BusId(bus_id), bus_id, 10.0))
    network.add_source(Source(SourceId("SRC"), "Grid", BusId("B1"), 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0))
    network.add_switch(
        Switch(SwitchId("SW1"), "SW1", BusId("B2"), BusId("B3"), closed=False)
    )

    boundaries = find_open_switch_boundaries(network, energized_buses(network))

    assert len(boundaries) == 1
    assert boundaries[0].from_energized is True
    assert boundaries[0].to_energized is False
    assert boundaries[0].separates_energized_from_deenergized is True


def test_meshed_roots_are_reported_as_feeder_overlaps() -> None:
    network = NetworkModel()
    for bus_id in ("B0", "B1", "B2"):
        network.add_bus(Bus(BusId(bus_id), bus_id, 10.0))
    network.add_source(Source(SourceId("SRC"), "Grid", BusId("B0"), 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B0"), BusId("B1"), 0.1, 10.0))
    network.add_line(Line(LineId("L2"), "L2", BusId("B0"), BusId("B2"), 0.1, 10.0))
    network.add_line(Line(LineId("TIE"), "TIE", BusId("B1"), BusId("B2"), 0.1, 10.0))

    overlaps = find_feeder_overlaps(trace_feeders(network))

    assert {item.bus_id for item in overlaps} == {"B1", "B2"}
    assert all(len(item.feeder_ids) == 2 for item in overlaps)


def test_feeder_trace_stops_expansion_at_other_source_bus() -> None:
    network = NetworkModel()
    for bus_id in ("B0", "B1", "B2"):
        network.add_bus(Bus(BusId(bus_id), bus_id, 10.0))
    network.add_source(Source(SourceId("S1"), "S1", BusId("B0"), 10.0))
    network.add_source(Source(SourceId("S2"), "S2", BusId("B2"), 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B0"), BusId("B1"), 0.1, 10.0))
    network.add_line(Line(LineId("L2"), "L2", BusId("B1"), BusId("B2"), 0.1, 10.0))

    feeder = [item for item in trace_feeders(network) if item.source_id == "S1"][0]

    assert feeder.buses == frozenset({"B0", "B1", "B2"})
    assert "B2" in feeder.boundary_buses
