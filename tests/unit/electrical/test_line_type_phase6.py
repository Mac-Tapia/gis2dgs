import pytest

from gis2dgs.electrical import LineType


def _type(**overrides: object) -> LineType:
    data: dict[str, object] = {
        "id": "LT1",
        "name": "Synthetic line type",
        "nominal_voltage_kv": 10.0,
        "r1_ohm_per_km": 0.5,
        "x1_ohm_per_km": 0.3,
        "rated_current_a": 200.0,
        "c1_nf_per_km": 8.0,
        "r0_ohm_per_km": 1.0,
        "x0_ohm_per_km": 0.9,
        "c0_nf_per_km": 4.0,
    }
    data.update(overrides)
    return LineType(**data)  # type: ignore[arg-type]


def test_line_type_calculates_sequence_impedance() -> None:
    line_type = _type()
    assert line_type.series_impedance_ohm(2.0) == complex(1.0, 0.6)
    assert line_type.series_impedance_ohm(2.0, sequence=0) == complex(2.0, 1.8)
    assert line_type.shunt_capacitance_nf(2.0) == pytest.approx(16.0)


def test_line_type_requires_complete_zero_sequence_triplet() -> None:
    with pytest.raises(ValueError, match="Zero-sequence"):
        _type(x0_ohm_per_km=None)


def test_line_type_rejects_invalid_phases() -> None:
    with pytest.raises(ValueError, match="phases"):
        _type(phases=4)


def test_line_type_rejects_non_finite_parameter() -> None:
    with pytest.raises(ValueError, match="finite"):
        _type(r1_ohm_per_km=float("nan"))


def test_zero_sequence_calculation_requires_data() -> None:
    line_type = _type(r0_ohm_per_km=None, x0_ohm_per_km=None, c0_nf_per_km=None)
    assert not line_type.has_zero_sequence_data
    with pytest.raises(ValueError, match="no zero-sequence"):
        line_type.series_impedance_ohm(1.0, sequence=0)


def test_line_type_rejects_invalid_runtime_sequence() -> None:
    line_type = _type()
    with pytest.raises(ValueError, match="sequence"):
        line_type.series_impedance_ohm(1.0, sequence=2)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="sequence"):
        line_type.shunt_capacitance_nf(1.0, sequence=2)  # type: ignore[arg-type]


def test_line_type_rejects_non_positive_length() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        _type().series_impedance_ohm(0.0)
