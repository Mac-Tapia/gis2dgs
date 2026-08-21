import pytest
from pydantic import ValidationError

from gis2dgs.config.models import MappingConfig


def test_mapping_config_accepts_known_sections() -> None:
    config = MappingConfig.model_validate(
        {
            "target_crs": "EPSG:4326",
            "buses": {
                "source": "nodes",
                "fields": {"id": "node_id"},
                "units": {"nominal_voltage_kv": "V"},
                "defaults": {"in_service": True},
            },
        }
    )
    assert config.buses is not None
    assert config.buses.source == "nodes"
    assert config.target_crs == "EPSG:4326"


def test_mapping_config_rejects_unknown_sections() -> None:
    with pytest.raises(ValidationError):
        MappingConfig.model_validate({"unknown": {"source": "x"}})


def test_layer_mapping_rejects_blank_source() -> None:
    with pytest.raises(ValidationError):
        MappingConfig.model_validate({"buses": {"source": "   "}})


def test_layer_mapping_rejects_unknown_units() -> None:
    with pytest.raises(ValidationError):
        MappingConfig.model_validate(
            {
                "buses": {
                    "source": "nodes",
                    "units": {"nominal_voltage_kv": "MV"},
                }
            }
        )


def test_mapping_config_accepts_generators_section() -> None:
    config = MappingConfig.model_validate(
        {
            "generators": {
                "source": "generators",
                "fields": {
                    "id": "generator_id",
                    "bus_id": "node_id",
                    "active_power_mw": "p_kw",
                },
                "units": {"active_power_mw": "kW"},
            }
        }
    )
    assert config.generators is not None
    assert config.generators.source == "generators"
