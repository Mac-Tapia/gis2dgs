import pytest

from gis2dgs.domain.bus import Bus
from gis2dgs.domain.identifiers import BusId
from gis2dgs.domain.network import NetworkModel


def test_add_bus() -> None:
    network = NetworkModel()
    bus = Bus(BusId("BUS_001"), "Barra 10 kV", 10.0)
    network.add_bus(bus)
    assert network.buses[BusId("BUS_001")] == bus


def test_duplicate_bus_is_rejected() -> None:
    network = NetworkModel()
    bus = Bus(BusId("BUS_001"), "Barra 10 kV", 10.0)
    network.add_bus(bus)
    with pytest.raises(ValueError):
        network.add_bus(bus)


def test_add_generator_and_reject_duplicate() -> None:
    from gis2dgs.domain import BusId, Generator, GeneratorId

    network = NetworkModel()
    generator = Generator(GeneratorId("G1"), "G1", BusId("B1"), 0.1)
    network.add_generator(generator)
    assert network.generators[GeneratorId("G1")] == generator
    with pytest.raises(ValueError, match="Duplicate generator ID"):
        network.add_generator(generator)
