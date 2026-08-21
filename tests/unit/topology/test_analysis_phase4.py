from gis2dgs.domain import (
    Bus,
    BusId,
    Line,
    LineId,
    NetworkModel,
    Source,
    SourceId,
    Switch,
    SwitchId,
)
from gis2dgs.topology import (
    CycleKind,
    build_graph,
    deenergized_buses,
    energized_buses,
    find_cycles,
    find_islands,
    trace_sources,
)


def _network_with_open_boundary() -> NetworkModel:
    network = NetworkModel()
    for bus_id in ("B1", "B2", "B3"):
        network.add_bus(Bus(BusId(bus_id), bus_id, 10.0))
    network.add_source(Source(SourceId("SRC"), "Grid", BusId("B1"), 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0))
    network.add_switch(
        Switch(SwitchId("SW1"), "SW1", BusId("B2"), BusId("B3"), closed=False)
    )
    return network


def test_source_trace_and_energization_respect_open_switch() -> None:
    network = _network_with_open_boundary()
    graph = build_graph(network)

    traces = trace_sources(network, graph)

    assert len(traces) == 1
    assert traces[0].buses == frozenset({"B1", "B2"})
    assert energized_buses(network, graph) == frozenset({"B1", "B2"})
    assert deenergized_buses(network, graph) == frozenset({"B3"})


def test_find_islands_marks_source_component_energized() -> None:
    islands = find_islands(_network_with_open_boundary())

    assert len(islands) == 2
    assert islands[0].buses == frozenset({"B1", "B2"})
    assert islands[0].energized is True
    assert islands[0].radial is True
    assert islands[1].buses == frozenset({"B3"})
    assert islands[1].energized is False


def test_find_cycles_detects_simple_loop() -> None:
    network = NetworkModel()
    for bus_id in ("B1", "B2", "B3"):
        network.add_bus(Bus(BusId(bus_id), bus_id, 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0))
    network.add_line(Line(LineId("L2"), "L2", BusId("B2"), BusId("B3"), 0.1, 10.0))
    network.add_line(Line(LineId("L3"), "L3", BusId("B3"), BusId("B1"), 0.1, 10.0))

    cycles = find_cycles(build_graph(network))

    assert len(cycles) == 1
    assert cycles[0].kind is CycleKind.SIMPLE
    assert set(cycles[0].buses) == {"B1", "B2", "B3"}


def test_find_cycles_detects_parallel_elements() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0))
    network.add_line(Line(LineId("L2"), "L2", BusId("B1"), BusId("B2"), 0.1, 10.0))

    cycles = find_cycles(build_graph(network))

    assert len(cycles) == 1
    assert cycles[0].kind is CycleKind.PARALLEL
    assert {edge.object_id for edge in cycles[0].edges} == {"L1", "L2"}
