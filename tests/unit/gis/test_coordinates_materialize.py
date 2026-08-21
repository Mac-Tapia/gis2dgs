import geopandas as gpd

from gis2dgs.config.models import LayerMapping, MappingConfig
from gis2dgs.gis.coordinates import materialize_layer_points, materialize_mapped_coordinates
from gis2dgs.gis.dataset import GisDataset


def test_materialize_layer_points_from_xy_mapping() -> None:
    frame = gpd.GeoDataFrame({"UTMEste": [500000.0], "UTMNorte": [9500000.0]})
    mapping = LayerMapping(source="nodes", fields={"x": "UTMEste", "y": "UTMNorte"})
    updated = materialize_layer_points(frame, mapping, default_crs="EPSG:32718")
    assert updated.crs is not None
    assert updated.geometry.iloc[0].x == 500000.0
    assert updated.geometry.iloc[0].y == 9500000.0


def test_materialize_layer_points_without_active_geometry_or_crs() -> None:
    frame = gpd.GeoDataFrame({"UTMEste": [500000.0], "UTMNorte": [9500000.0]})
    mapping = LayerMapping(source="nodes", fields={"x": "UTMEste", "y": "UTMNorte"})
    updated = materialize_layer_points(frame, mapping)
    assert updated.geometry.iloc[0].x == 500000.0
    assert updated.geometry.iloc[0].y == 9500000.0


def test_materialize_mapped_coordinates_for_bus_layer() -> None:
    dataset = GisDataset()
    dataset.add_layer(
        "mtNodoEnlace",
        gpd.GeoDataFrame({"CodNodoMT": ["B1"], "UTMEste": [1.0], "UTMNorte": [2.0]}),
    )
    mapping = MappingConfig(
        buses=LayerMapping(
            source="mtNodoEnlace",
            fields={"id": "CodNodoMT", "x": "UTMEste", "y": "UTMNorte"},
        )
    )
    updated = materialize_mapped_coordinates(dataset, mapping, default_crs="EPSG:32718")
    geometry = updated.layer("mtNodoEnlace").geometry.iloc[0]
    assert geometry.x == 1.0
    assert geometry.y == 2.0
