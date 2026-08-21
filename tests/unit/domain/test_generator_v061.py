import pytest

from gis2dgs.domain import BusId, Generator, GeneratorId


def test_generator_accepts_generation_and_optional_technology() -> None:
    generator = Generator(
        GeneratorId("PV1"),
        "PV rooftop",
        BusId("B1"),
        0.25,
        -0.01,
        technology="PV",
    )
    assert generator.active_power_mw == pytest.approx(0.25)
    assert generator.reactive_power_mvar == pytest.approx(-0.01)
    assert generator.technology == "PV"


def test_generator_rejects_negative_active_power() -> None:
    with pytest.raises(ValueError, match="active power cannot be negative"):
        Generator(GeneratorId("G1"), "G1", BusId("B1"), -0.1)


def test_generator_rejects_blank_technology() -> None:
    with pytest.raises(ValueError, match="technology cannot be blank"):
        Generator(GeneratorId("G1"), "G1", BusId("B1"), 0.1, technology="  ")
