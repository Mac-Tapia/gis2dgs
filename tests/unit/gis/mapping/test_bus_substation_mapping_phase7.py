import geopandas as gpd

from gis2dgs.config.models import LayerMapping, MappingConfig
from gis2dgs.domain.identifiers import BusId, SubstationId
from gis2dgs.gis import GisDataset
from gis2dgs.gis.mapping.domain_mapper import GisToDomainMapper


def test_gis_mapper_can_map_optional_bus_substation_reference() -> None:
    dataset = GisDataset(
        {
            "nodes": gpd.GeoDataFrame(
                {
                    "node_id": ["B1"],
                    "name": ["Bus 1"],
                    "kv": [10.0],
                    "station": ["S1"],
                }
            ),
            "stations": gpd.GeoDataFrame(
                {"station_id": ["S1"], "station_name": ["Substation 1"]}
            ),
        }
    )
    config = MappingConfig(
        buses=LayerMapping(
            source="nodes",
            fields={
                "id": "node_id",
                "name": "name",
                "nominal_voltage_kv": "kv",
                "substation_id": "station",
            },
        ),
        substations=LayerMapping(
            source="stations",
            fields={"id": "station_id", "name": "station_name"},
        ),
    )

    network = GisToDomainMapper(config).map(dataset)

    assert network.buses[BusId("B1")].substation_id == SubstationId("S1")
