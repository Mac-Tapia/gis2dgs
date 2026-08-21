import pytest

from gis2dgs.electrical import TransformerType


def _type(**overrides: object) -> TransformerType:
    data: dict[str, object] = {
        "id": "TT1",
        "name": "Synthetic transformer type",
        "rated_power_mva": 1.0,
        "hv_voltage_kv": 10.0,
        "lv_voltage_kv": 0.4,
        "uk_percent": 6.0,
        "copper_loss_kw": 10.0,
        "no_load_loss_kw": 2.0,
        "no_load_current_percent": 1.0,
        "vector_group": "Dyn11",
    }
    data.update(overrides)
    return TransformerType(**data)  # type: ignore[arg-type]


def test_transformer_type_derives_short_circuit_components() -> None:
    transformer_type = _type()
    assert transformer_type.short_circuit_r_percent == pytest.approx(1.0)
    assert transformer_type.short_circuit_x_percent == pytest.approx(5.9160797831)
    assert transformer_type.base_impedance_ohm("hv") == pytest.approx(100.0)
    impedance = transformer_type.short_circuit_impedance_ohm("hv")
    assert impedance.real == pytest.approx(1.0)
    assert impedance.imag == pytest.approx(5.9160797831)


def test_transformer_type_rejects_inconsistent_copper_loss() -> None:
    with pytest.raises(ValueError, match="copper loss"):
        _type(copper_loss_kw=100.0, uk_percent=5.0)


def test_transformer_zero_sequence_is_all_or_nothing() -> None:
    with pytest.raises(ValueError, match="zero-sequence"):
        _type(uk0_percent=6.0)


def test_transformer_zero_sequence_flag() -> None:
    transformer_type = _type(uk0_percent=6.0, ur0_percent=1.0)
    assert transformer_type.has_zero_sequence_data


def test_transformer_type_rejects_invalid_side() -> None:
    with pytest.raises(ValueError, match="side"):
        _type().base_impedance_ohm("mv")  # type: ignore[arg-type]


def test_transformer_type_rejects_zero_sequence_resistance_above_impedance() -> None:
    with pytest.raises(ValueError, match="ur0_percent"):
        _type(uk0_percent=5.0, ur0_percent=6.0)


def test_transformer_type_rejects_invalid_basic_fields() -> None:
    with pytest.raises(ValueError, match="id"):
        _type(id="")
    with pytest.raises(ValueError, match="HV voltage"):
        _type(hv_voltage_kv=0.4, lv_voltage_kv=0.4)
    with pytest.raises(ValueError, match="cannot exceed"):
        _type(uk_percent=101.0)
