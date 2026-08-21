from gis2dgs.domain import Bus, Line, NetworkModel
from gis2dgs.domain.identifiers import BusId, LineId
from gis2dgs.powerfactory import PowerFactoryMapper, PowerFactoryMappingPolicy


def test_cubicles_carry_connection_index() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 1.0, 10.0))
    policy = PowerFactoryMappingPolicy(require_type_references=False)

    model = PowerFactoryMapper(policy).map(network)
    cubicles = [obj for obj in model.objects.values() if obj.class_name == "StaCubic"]

    assert sorted(obj.attributes["connection_index"] for obj in cubicles) == [0, 1]


def test_policy_can_create_closed_staswitch_per_cubicle() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 1.0, 10.0))
    policy = PowerFactoryMappingPolicy(
        require_type_references=False,
        create_cubicle_switches=True,
    )

    model = PowerFactoryMapper(policy).map(network)
    switches = [obj for obj in model.objects.values() if obj.class_name == "StaSwitch"]

    assert len(switches) == 2
    assert all(obj.attributes["closed"] is True for obj in switches)
    assert all(obj.parent is not None for obj in switches)
