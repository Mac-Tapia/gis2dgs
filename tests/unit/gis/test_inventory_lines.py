import geopandas as gpd
from shapely.geometry import LineString

from gis2dgs.config.models import LayerMapping, MappingConfig
from gis2dgs.domain import NetworkModel
from gis2dgs.domain.bus import Bus
from gis2dgs.domain.identifiers import BusId
from gis2dgs.gis.dataset import GisDataset
from gis2dgs.gis.inventory_lines import augment_network_lines_from_geometry


def test_augment_network_lines_from_geometry_uses_span_coordinates() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("N1"), "N1", 1.0, x=0.0, y=0.0))
    network.add_bus(Bus(BusId("N2"), "N2", 1.0, x=100.0, y=0.0))

    dataset = GisDataset()
    dataset.add_layer(
        "EQPM",
        gpd.GeoDataFrame(
            {"id0": ["L1"], "geometry": [LineString([(0.0, 0.0), (100.0, 0.0)])]},
            crs="EPSG:32718",
        ),
    )
    mapping = MappingConfig(
        buses=LayerMapping(source="NMT", fields={"id": "id", "x": "x", "y": "y"}),
        lines=LayerMapping(
            source="EQPM",
            fields={"id": "id0"},
            defaults={"nominal_voltage_kv": 1.0, "length_km": 0.1},
        ),
    )

    created = augment_network_lines_from_geometry(network, dataset, mapping)

    assert created == 1
    line = next(iter(network.lines.values()))
    assert str(line.from_bus) == "N1"
    assert str(line.to_bus) == "N2"


def test_augment_network_lines_from_geometry_snaps_to_nearest_bus_within_tolerance() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("N1"), "N1", 1.0, x=0.0, y=0.0))
    network.add_bus(Bus(BusId("N2"), "N2", 1.0, x=100.0, y=0.0))

    dataset = GisDataset()
    dataset.add_layer(
        "EQPM",
        gpd.GeoDataFrame(
            {
                "id0": ["L1"],
                "geometry": [LineString([(1.5, 0.0), (98.5, 0.0)])],
            },
            crs="EPSG:32718",
        ),
    )
    mapping = MappingConfig(
        buses=LayerMapping(source="NMT", fields={"id": "id", "x": "x", "y": "y"}),
        lines=LayerMapping(
            source="EQPM",
            fields={"id": "id0"},
            defaults={"nominal_voltage_kv": 1.0, "length_km": 0.1},
        ),
        connectivity={"tolerance_m": 2.0},
    )

    created = augment_network_lines_from_geometry(network, dataset, mapping)

    assert created == 1
    line = next(iter(network.lines.values()))
    assert str(line.from_bus) == "N1"
    assert str(line.to_bus) == "N2"
    assert not any(str(bus.id).startswith("GEO_") for bus in network.buses.values())
