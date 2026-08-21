from gis2dgs.domain import Bus, BusId, NetworkModel, Switch, SwitchId
from gis2dgs.topology import build_graph, build_physical_graph


def test_physical_graph_keeps_open_switch_as_non_conductive() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_switch(
        Switch(SwitchId("SW1"), "SW1", BusId("B1"), BusId("B2"), closed=False)
    )

    conductive = build_graph(network)
    physical = build_physical_graph(network)

    assert not conductive.has_edge("B1", "B2")
    assert physical.has_edge("B1", "B2", "switch:SW1")
    assert physical["B1"]["B2"]["switch:SW1"]["conductive"] is False
