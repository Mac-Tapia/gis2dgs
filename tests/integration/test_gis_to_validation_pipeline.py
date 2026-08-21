import geopandas as gpd
from shapely.geometry import Point

from gis2dgs.config.models import MappingConfig
from gis2dgs.gis.dataset import GisDataset
from gis2dgs.gis.mapping.domain_mapper import GisToDomainMapper
from gis2dgs.validation.validator import NetworkValidator


def test_gis_mapping_output_is_accepted_by_validation_pipeline() -> None:
    dataset = GisDataset()
    dataset.add_layer(
        "nodes",
        gpd.GeoDataFrame(
            {"id": ["B1", "B2"], "v": [10000, 10000]},
            geometry=[Point(0, 0), Point(1, 0)],
            crs="EPSG:4326",
        ),
    )
    dataset.add_layer(
        "lines",
        gpd.GeoDataFrame(
            {
                "id": ["L1"],
                "f": ["B1"],
                "t": ["B2"],
                "m": [100],
                "v": [10000],
            },
            geometry=[None],
            crs="EPSG:4326",
        ),
    )
    dataset.add_layer(
        "generators",
        gpd.GeoDataFrame(
            {"id": ["PV1"], "bus": ["B2"], "p_kw": [15.0], "q_kvar": [0.0]},
            geometry=[None],
            crs="EPSG:4326",
        ),
    )
    dataset.add_layer(
        "sources",
        gpd.GeoDataFrame(
            {"id": ["GRID"], "bus": ["B1"], "v": [10000]},
            geometry=[None],
            crs="EPSG:4326",
        ),
    )
    config = MappingConfig.model_validate(
        {
            "buses": {
                "source": "nodes",
                "fields": {"id": "id", "nominal_voltage_kv": "v"},
                "units": {"nominal_voltage_kv": "V"},
            },
            "lines": {
                "source": "lines",
                "fields": {
                    "id": "id",
                    "from_bus": "f",
                    "to_bus": "t",
                    "length_km": "m",
                    "nominal_voltage_kv": "v",
                },
                "units": {"length_km": "m", "nominal_voltage_kv": "V"},
            },
            "generators": {
                "source": "generators",
                "fields": {
                    "id": "id",
                    "bus_id": "bus",
                    "active_power_mw": "p_kw",
                    "reactive_power_mvar": "q_kvar",
                },
                "units": {
                    "active_power_mw": "kW",
                    "reactive_power_mvar": "kvar",
                },
            },
            "sources": {
                "source": "sources",
                "fields": {"id": "id", "bus_id": "bus", "nominal_voltage_kv": "v"},
                "units": {"nominal_voltage_kv": "V"},
            },
        }
    )

    network = GisToDomainMapper(config).map(dataset)
    issues = NetworkValidator().validate(network)

    assert network.summary()["generators"] == 1
    assert issues.issues == []
    assert issues.is_valid is True
