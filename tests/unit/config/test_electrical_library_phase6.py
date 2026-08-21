from pathlib import Path

import pytest
from pydantic import ValidationError

from gis2dgs.config import load_electrical_library, parse_electrical_library


def _valid_data() -> dict[str, object]:
    return {
        "line_types": {
            "LT1": {
                "name": "Synthetic line",
                "nominal_voltage_kv": 10.0,
                "r1_ohm_per_km": 0.4,
                "x1_ohm_per_km": 0.3,
                "rated_current_a": 200.0,
            }
        },
        "transformer_types": {
            "TT1": {
                "name": "Synthetic transformer",
                "rated_power_mva": 1.0,
                "hv_voltage_kv": 10.0,
                "lv_voltage_kv": 0.4,
                "uk_percent": 6.0,
                "copper_loss_kw": 10.0,
                "no_load_loss_kw": 2.0,
                "no_load_current_percent": 1.0,
                "vector_group": "Dyn11",
            }
        },
    }


def test_parse_electrical_library_builds_domain_library() -> None:
    library = parse_electrical_library(_valid_data())
    assert library.summary()["total_types"] == 2
    assert library.get_line_type("LT1").nominal_voltage_kv == 10.0


def test_loader_reads_yaml(tmp_path: Path) -> None:
    path = tmp_path / "library.yaml"
    path.write_text(
        """
line_types:
  LT1:
    name: Synthetic line
    nominal_voltage_kv: 10.0
    r1_ohm_per_km: 0.4
    x1_ohm_per_km: 0.3
    rated_current_a: 200.0
transformer_types: {}
""".lstrip(),
        encoding="utf-8",
    )
    library = load_electrical_library(path)
    assert library.get_line_type("LT1").rated_current_a == 200.0


def test_config_rejects_unknown_fields() -> None:
    data = _valid_data()
    line_data = data["line_types"]  # type: ignore[index]
    line_data["LT1"]["unexpected"] = 3  # type: ignore[index]
    with pytest.raises(ValidationError):
        parse_electrical_library(data)


def test_repository_default_library_is_intentionally_empty() -> None:
    project_root = Path(__file__).resolve().parents[3]
    library = load_electrical_library(project_root / "config" / "electrical_library.yaml")
    assert library.is_empty


def test_domain_semantics_reject_invalid_positive_sequence_resistance() -> None:
    data = _valid_data()
    line_data = data["line_types"]  # type: ignore[index]
    line_data["LT1"]["r1_ohm_per_km"] = 0.0  # type: ignore[index]
    with pytest.raises(ValueError, match="r1_ohm_per_km"):
        parse_electrical_library(data)
