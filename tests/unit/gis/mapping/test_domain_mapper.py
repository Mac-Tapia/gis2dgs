import geopandas as gpd
import pytest
from shapely.geometry import Point

from gis2dgs.config.models import MappingConfig
from gis2dgs.domain.identifiers import (
    BusId,
    GeneratorId,
    LineId,
    LoadId,
    SourceId,
    TransformerId,
)
from gis2dgs.gis.dataset import GisDataset
from gis2dgs.gis.exceptions import GisMappingError
from gis2dgs.gis.mapping.domain_mapper import GisToDomainMapper


def _dataset() -> GisDataset:
    dataset = GisDataset()
    dataset.add_layer(
        "nodes",
        gpd.GeoDataFrame(
            {
                "node_id": ["B1", "B2", "B3"],
                "node_name": ["Barra 1", None, "Barra 3"],
                "voltage_v": [10000, 10000, 400],
                "feeder": ["F1", "F1", None],
            },
            geometry=[Point(1, 2), Point(2, 3), Point(3, 4)],
            crs="EPSG:4326",
        ),
    )
    dataset.add_layer(
        "lines",
        gpd.GeoDataFrame(
            {
                "line_id": ["L1"],
                "from_node": ["B1"],
                "to_node": ["B2"],
                "length_m": [150.0],
                "voltage_v": [10000],
                "conductor": ["AAAC70"],
                "status": ["ACTIVO"],
            },
            geometry=[None],
            crs="EPSG:4326",
        ),
    )
    dataset.add_layer(
        "transformers",
        gpd.GeoDataFrame(
            {
                "trafo_id": ["T1"],
                "hv": ["B2"],
                "lv": ["B3"],
                "vhv": [10000],
                "vlv": [400],
                "kva": [630],
            },
            geometry=[None],
            crs="EPSG:4326",
        ),
    )
    dataset.add_layer(
        "loads",
        gpd.GeoDataFrame(
            {
                "load_id": ["LD1"],
                "bus": ["B3"],
                "p_kw": [50.0],
                "q_kvar": [20.0],
            },
            geometry=[None],
            crs="EPSG:4326",
        ),
    )
    dataset.add_layer(
        "generators",
        gpd.GeoDataFrame(
            {
                "generator_id": ["PV1"],
                "bus": ["B3"],
                "p_kw": [25.0],
                "q_kvar": [-5.0],
                "technology": ["PV"],
            },
            geometry=[None],
            crs="EPSG:4326",
        ),
    )
    dataset.add_layer(
        "sources",
        gpd.GeoDataFrame(
            {"source_id": ["GRID"], "bus": ["B1"], "voltage_v": [10000]},
            geometry=[None],
            crs="EPSG:4326",
        ),
    )
    return dataset


def _config() -> MappingConfig:
    return MappingConfig.model_validate(
        {
            "buses": {
                "source": "nodes",
                "fields": {
                    "id": "node_id",
                    "name": "node_name",
                    "nominal_voltage_kv": "voltage_v",
                    "feeder_id": "feeder",
                },
                "units": {"nominal_voltage_kv": "V"},
            },
            "lines": {
                "source": "lines",
                "fields": {
                    "id": "line_id",
                    "from_bus": "from_node",
                    "to_bus": "to_node",
                    "length_km": "length_m",
                    "nominal_voltage_kv": "voltage_v",
                    "type_id": "conductor",
                    "in_service": "status",
                },
                "units": {"length_km": "m", "nominal_voltage_kv": "V"},
            },
            "transformers": {
                "source": "transformers",
                "fields": {
                    "id": "trafo_id",
                    "hv_bus": "hv",
                    "lv_bus": "lv",
                    "hv_voltage_kv": "vhv",
                    "lv_voltage_kv": "vlv",
                    "rated_power_mva": "kva",
                },
                "units": {
                    "hv_voltage_kv": "V",
                    "lv_voltage_kv": "V",
                    "rated_power_mva": "kVA",
                },
            },
            "loads": {
                "source": "loads",
                "fields": {
                    "id": "load_id",
                    "bus_id": "bus",
                    "active_power_mw": "p_kw",
                    "reactive_power_mvar": "q_kvar",
                },
                "units": {
                    "active_power_mw": "kW",
                    "reactive_power_mvar": "kvar",
                },
            },
            "generators": {
                "source": "generators",
                "fields": {
                    "id": "generator_id",
                    "bus_id": "bus",
                    "active_power_mw": "p_kw",
                    "reactive_power_mvar": "q_kvar",
                    "technology": "technology",
                },
                "units": {
                    "active_power_mw": "kW",
                    "reactive_power_mvar": "kvar",
                },
            },
            "sources": {
                "source": "sources",
                "fields": {
                    "id": "source_id",
                    "bus_id": "bus",
                    "nominal_voltage_kv": "voltage_v",
                },
                "units": {"nominal_voltage_kv": "V"},
            },
        }
    )


def test_mapper_builds_canonical_network_and_normalizes_units() -> None:
    network = GisToDomainMapper(_config()).map(_dataset())

    assert network.summary() == {
        "buses": 3,
        "lines": 1,
        "transformers": 1,
        "switches": 0,
        "loads": 1,
        "generators": 1,
        "sources": 1,
        "substations": 0,
    }
    assert network.buses[BusId("B1")].nominal_voltage_kv == pytest.approx(10.0)
    assert network.buses[BusId("B1")].x == pytest.approx(1.0)
    assert network.buses[BusId("B2")].name == "B2"
    assert network.lines[LineId("L1")].length_km == pytest.approx(0.15)
    assert network.lines[LineId("L1")].type_id == "AAAC70"
    assert network.transformers[TransformerId("T1")].rated_power_mva == pytest.approx(0.63)
    assert network.loads[LoadId("LD1")].active_power_mw == pytest.approx(0.05)
    assert network.loads[LoadId("LD1")].reactive_power_mvar == pytest.approx(0.02)
    generator = network.generators[GeneratorId("PV1")]
    assert generator.active_power_mw == pytest.approx(0.025)
    assert generator.reactive_power_mvar == pytest.approx(-0.005)
    assert generator.technology == "PV"
    assert network.sources[SourceId("GRID")].nominal_voltage_kv == pytest.approx(10.0)


def test_mapper_supports_defaults_and_decimal_comma() -> None:
    dataset = GisDataset()
    dataset.add_layer(
        "nodes",
        gpd.GeoDataFrame(
            {"id": ["B1"], "voltage": ["22,9"]},
            geometry=[Point(-77, -12)],
            crs="EPSG:4326",
        ),
    )
    config = MappingConfig.model_validate(
        {
            "buses": {
                "source": "nodes",
                "fields": {"id": "id", "nominal_voltage_kv": "voltage"},
            }
        }
    )

    network = GisToDomainMapper(config).map(dataset)

    assert network.buses[BusId("B1")].name == "B1"
    assert network.buses[BusId("B1")].nominal_voltage_kv == pytest.approx(22.9)


def test_mapper_reports_layer_row_context_for_invalid_data() -> None:
    dataset = GisDataset()
    dataset.add_layer(
        "nodes",
        gpd.GeoDataFrame(
            {"id": ["B1"], "voltage": [0]},
            geometry=[Point(0, 0)],
            crs="EPSG:4326",
        ),
    )
    config = MappingConfig.model_validate(
        {
            "buses": {
                "source": "nodes",
                "fields": {"id": "id", "nominal_voltage_kv": "voltage"},
            }
        }
    )

    with pytest.raises(GisMappingError, match="Layer 'nodes', row 0"):
        GisToDomainMapper(config).map(dataset)


def test_mapper_uses_explicit_xy_columns_over_point_geometry() -> None:
    dataset = GisDataset()
    dataset.add_layer(
        "nodes",
        gpd.GeoDataFrame(
            {"id": ["B1"], "voltage": [10], "coord_x": [100.0], "coord_y": [200.0]},
            geometry=[Point(1, 2)],
            crs="EPSG:4326",
        ),
    )
    config = MappingConfig.model_validate(
        {
            "buses": {
                "source": "nodes",
                "fields": {
                    "id": "id",
                    "nominal_voltage_kv": "voltage",
                    "x": "coord_x",
                    "y": "coord_y",
                },
            }
        }
    )

    bus = GisToDomainMapper(config).map(dataset).buses[BusId("B1")]

    assert bus.x == pytest.approx(100.0)
    assert bus.y == pytest.approx(200.0)


def test_mapper_reprojects_geometry_before_extracting_coordinates() -> None:
    dataset = GisDataset()
    dataset.add_layer(
        "nodes",
        gpd.GeoDataFrame(
            {"id": ["B1"], "voltage": [10]},
            geometry=[Point(-77.0, -12.0)],
            crs="EPSG:4326",
        ),
    )
    config = MappingConfig.model_validate(
        {
            "target_crs": "EPSG:3857",
            "buses": {
                "source": "nodes",
                "fields": {"id": "id", "nominal_voltage_kv": "voltage"},
            },
        }
    )

    bus = GisToDomainMapper(config).map(dataset).buses[BusId("B1")]

    assert bus.x is not None
    assert bus.x != pytest.approx(-77.0)


def test_duplicate_domain_ids_keep_first_occurrence() -> None:
    dataset = GisDataset()
    dataset.add_layer(
        "nodes",
        gpd.GeoDataFrame(
            {"id": ["B1", "B1"], "voltage": [10, 10]},
            geometry=[Point(0, 0), Point(1, 1)],
            crs="EPSG:4326",
        ),
    )
    config = MappingConfig.model_validate(
        {
            "buses": {
                "source": "nodes",
                "fields": {"id": "id", "nominal_voltage_kv": "voltage"},
            }
        }
    )

    network = GisToDomainMapper(config).map(dataset)
    assert len(network.buses) == 1
    assert network.buses[BusId("B1")].nominal_voltage_kv == 10.0


def test_mapper_builds_switch_and_substation() -> None:
    dataset = GisDataset()
    dataset.add_layer(
        "nodes",
        gpd.GeoDataFrame(
            {"id": ["B1", "B2"], "v": [10, 10]},
            geometry=[Point(0, 0), Point(1, 0)],
            crs="EPSG:4326",
        ),
    )
    dataset.add_layer(
        "switches",
        gpd.GeoDataFrame(
            {
                "id": ["SW1"],
                "f": ["B1"],
                "t": ["B2"],
                "state": ["ABIERTO"],
                "service": ["ACTIVO"],
            },
            geometry=[None],
            crs="EPSG:4326",
        ),
    )
    dataset.add_layer(
        "substations",
        gpd.GeoDataFrame(
            {"id": ["SE1"], "name": ["Subestación 1"]},
            geometry=[Point(-73.25, -3.74)],
            crs="EPSG:4326",
        ),
    )
    config = MappingConfig.model_validate(
        {
            "buses": {
                "source": "nodes",
                "fields": {"id": "id", "nominal_voltage_kv": "v"},
            },
            "switches": {
                "source": "switches",
                "fields": {
                    "id": "id",
                    "from_bus": "f",
                    "to_bus": "t",
                    "closed": "state",
                    "in_service": "service",
                },
            },
            "substations": {
                "source": "substations",
                "fields": {"id": "id", "name": "name"},
            },
        }
    )

    network = GisToDomainMapper(config).map(dataset)

    assert network.switches[next(iter(network.switches))].closed is False
    substation = network.substations[next(iter(network.substations))]
    assert substation.name == "Subestación 1"
    assert substation.x == pytest.approx(-73.25)
    assert substation.y == pytest.approx(-3.74)


def test_mapper_rejects_partial_xy_coordinates() -> None:
    dataset = GisDataset()
    dataset.add_layer(
        "nodes",
        gpd.GeoDataFrame(
            {"id": ["B1"], "v": [10], "x": [100.0]},
            geometry=[Point(1, 2)],
            crs="EPSG:4326",
        ),
    )
    config = MappingConfig.model_validate(
        {
            "buses": {
                "source": "nodes",
                "fields": {
                    "id": "id",
                    "nominal_voltage_kv": "v",
                    "x": "x",
                },
            }
        }
    )

    with pytest.raises(GisMappingError, match="Both x and y"):
        GisToDomainMapper(config).map(dataset)


def test_mapper_parses_geometry_text_column_for_coordinates() -> None:
    dataset = GisDataset()
    dataset.add_layer(
        "nodes",
        gpd.GeoDataFrame(
            {
                "id": ["B1"],
                "v": [10.0],
                "GEOMETRÍA": ["Nodo:  X- 421677.43  Y- 8453832.776"],
            }
        ),
    )
    config = MappingConfig.model_validate(
        {
            "buses": {
                "source": "nodes",
                "fields": {"id": "id", "nominal_voltage_kv": "v"},
            }
        }
    )
    network = GisToDomainMapper(config).map(dataset)
    bus = network.buses[BusId("B1")]
    assert bus.x == pytest.approx(421677.43)
    assert bus.y == pytest.approx(8453832.776)


def test_mapper_defaults_missing_load_active_power_to_zero(caplog) -> None:
    """Blank PAC/P cells must not abort NetworkModel construction."""

    import logging

    dataset = GisDataset()
    dataset.add_layer(
        "nodes",
        gpd.GeoDataFrame(
            {"id": ["B1"], "v": [10]},
            geometry=[Point(0, 0)],
            crs="EPSG:4326",
        ),
    )
    dataset.add_layer(
        "loads",
        gpd.GeoDataFrame(
            {
                "load_id": ["LD1", "LD2"],
                "bus": ["B1", "B1"],
                "p_kw": [50.0, None],
            },
            geometry=[None, None],
            crs="EPSG:4326",
        ),
    )
    config = MappingConfig.model_validate(
        {
            "buses": {
                "source": "nodes",
                "fields": {"id": "id", "nominal_voltage_kv": "v"},
            },
            "loads": {
                "source": "loads",
                "fields": {
                    "id": "load_id",
                    "bus_id": "bus",
                    "active_power_mw": "p_kw",
                },
                "units": {"active_power_mw": "kW"},
            },
        }
    )

    with caplog.at_level(logging.WARNING, logger="gis2dgs.gis.mapping.domain_mapper"):
        network = GisToDomainMapper(config).map(dataset)

    assert network.loads[LoadId("LD1")].active_power_mw == pytest.approx(0.05)
    assert network.loads[LoadId("LD2")].active_power_mw == pytest.approx(0.0)
    assert network.loads[LoadId("LD2")].reactive_power_mvar == pytest.approx(0.0)
    assert any("active_power_mw" in record.message for record in caplog.records)


def test_mapper_defaults_invalid_load_active_power_to_zero() -> None:
    dataset = GisDataset()
    dataset.add_layer(
        "nodes",
        gpd.GeoDataFrame(
            {"id": ["B1"], "v": [10]},
            geometry=[Point(0, 0)],
            crs="EPSG:4326",
        ),
    )
    dataset.add_layer(
        "loads",
        gpd.GeoDataFrame(
            {
                "load_id": ["LD1"],
                "bus": ["B1"],
                "p_kw": ["n/a"],
            },
            geometry=[None],
            crs="EPSG:4326",
        ),
    )
    config = MappingConfig.model_validate(
        {
            "buses": {
                "source": "nodes",
                "fields": {"id": "id", "nominal_voltage_kv": "v"},
            },
            "loads": {
                "source": "loads",
                "fields": {
                    "id": "load_id",
                    "bus_id": "bus",
                    "active_power_mw": "p_kw",
                },
                "units": {"active_power_mw": "kW"},
            },
        }
    )

    network = GisToDomainMapper(config).map(dataset)
    assert network.loads[LoadId("LD1")].active_power_mw == pytest.approx(0.0)


def test_mapper_skips_loads_with_missing_bus_id(caplog) -> None:
    import logging

    dataset = GisDataset()
    dataset.add_layer(
        "nodes",
        gpd.GeoDataFrame(
            {"id": ["B1"], "v": [10]},
            geometry=[Point(0, 0)],
            crs="EPSG:4326",
        ),
    )
    dataset.add_layer(
        "loads",
        gpd.GeoDataFrame(
            {
                "load_id": ["LD1", "LD2"],
                "bus": ["B1", None],
                "p_kw": [10.0, 20.0],
            },
            geometry=[None, None],
            crs="EPSG:4326",
        ),
    )
    config = MappingConfig.model_validate(
        {
            "buses": {
                "source": "nodes",
                "fields": {"id": "id", "nominal_voltage_kv": "v"},
            },
            "loads": {
                "source": "loads",
                "fields": {
                    "id": "load_id",
                    "bus_id": "bus",
                    "active_power_mw": "p_kw",
                },
                "units": {"active_power_mw": "kW"},
            },
        }
    )

    with caplog.at_level(logging.WARNING, logger="gis2dgs.gis.mapping.domain_mapper"):
        network = GisToDomainMapper(config).map(dataset)

    assert LoadId("LD1") in network.loads
    assert LoadId("LD2") not in network.loads
    assert any("bus_id" in record.message for record in caplog.records)


def test_mapper_uses_linestring_length_when_length_column_missing() -> None:
    from shapely.geometry import LineString

    dataset = GisDataset()
    dataset.add_layer(
        "nodes",
        gpd.GeoDataFrame(
            {"id": ["B1", "B2"], "v": [10, 10]},
            geometry=[Point(0, 0), Point(1000, 0)],
            crs="EPSG:32718",
        ),
    )
    dataset.add_layer(
        "lines",
        gpd.GeoDataFrame(
            {"id": ["L1"], "from_bus": ["B1"], "to_bus": ["B2"], "v": [10]},
            geometry=[LineString([(0, 0), (1000, 0)])],
            crs="EPSG:32718",
        ),
    )
    config = MappingConfig.model_validate(
        {
            "buses": {
                "source": "nodes",
                "fields": {"id": "id", "nominal_voltage_kv": "v"},
            },
            "lines": {
                "source": "lines",
                "fields": {
                    "id": "id",
                    "from_bus": "from_bus",
                    "to_bus": "to_bus",
                    "nominal_voltage_kv": "v",
                },
            },
        }
    )

    line = GisToDomainMapper(config).map(dataset).lines[LineId("L1")]
    assert line.length_km == pytest.approx(1.0)
