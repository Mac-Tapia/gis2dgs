import pytest

from gis2dgs.gis.normalizer import (
    convert_active_power_to_mw,
    convert_apparent_power_to_mva,
    convert_reactive_power_to_mvar,
    convert_voltage_to_kv,
    metres_to_km,
    normalize_identifier,
    normalize_number,
    normalize_optional_identifier,
    normalize_service_state,
    normalize_switch_state,
    volts_to_kv,
)


def test_volts_to_kv() -> None:
    assert volts_to_kv(22900.0) == pytest.approx(22.9)


def test_metres_to_km() -> None:
    assert metres_to_km(150.0) == pytest.approx(0.15)


@pytest.mark.parametrize("value", [True, 1, "C", "CERRADO", "ON", "true"])
def test_normalize_closed_switch(value: object) -> None:
    assert normalize_switch_state(value) is True


@pytest.mark.parametrize("value", [False, 0, "O", "ABIERTO", "OFF", "false"])
def test_normalize_open_switch(value: object) -> None:
    assert normalize_switch_state(value) is False


@pytest.mark.parametrize(
    "value",
    [True, 1, "ACTIVO", "EN SERVICIO", "E", "true", "CERRADO", "OPERATIVO", "INSTALADO"],
)
def test_normalize_in_service(value: object) -> None:
    assert normalize_service_state(value) is True


@pytest.mark.parametrize(
    "value",
    [False, 0, "INACTIVO", "FUERA DE SERVICIO", "false", "ABIERTO", "PROYECTADO"],
)
def test_normalize_out_of_service(value: object) -> None:
    assert normalize_service_state(value) is False


def test_identifier_strips_whitespace() -> None:
    assert normalize_identifier("  N001  ") == "N001"


def test_identifier_normalizes_integer_floats() -> None:
    assert normalize_identifier(1.0) == "1"
    assert normalize_identifier(123.0) == "123"
    assert normalize_identifier("45.0") == "45"
    assert normalize_optional_identifier(7.0) == "7"


def test_decimal_comma_is_supported() -> None:
    assert normalize_number("22,9") == pytest.approx(22.9)


def test_unit_conversions() -> None:
    assert convert_voltage_to_kv(22900, "V") == pytest.approx(22.9)
    assert convert_voltage_to_kv("60 KV") == pytest.approx(60.0)
    assert convert_voltage_to_kv("22,9 kV") == pytest.approx(22.9)
    assert convert_voltage_to_kv("22900 V") == pytest.approx(22.9)
    assert convert_active_power_to_mw(750, "kW") == pytest.approx(0.75)
    assert convert_reactive_power_to_mvar(250, "kvar") == pytest.approx(0.25)
    assert convert_apparent_power_to_mva(630, "kVA") == pytest.approx(0.63)


@pytest.mark.parametrize("unit", ["kV", "kv", "KV"])
def test_voltage_unit_is_case_insensitive(unit: str) -> None:
    assert convert_voltage_to_kv(10, unit) == pytest.approx(10.0)


def test_normalize_number_rejects_bool() -> None:
    with pytest.raises(ValueError, match="Boolean"):
        normalize_number(True)


def test_unknown_service_state_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported service state"):
        normalize_service_state("DESCONOCIDO")
