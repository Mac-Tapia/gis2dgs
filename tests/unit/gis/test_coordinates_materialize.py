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


def test_materialize_layer_linestrings_from_span_columns() -> None:
    from gis2dgs.gis.coordinates import materialize_layer_linestrings

    frame = gpd.GeoDataFrame(
        {
            "id0": ["L1"],
            "X1": [419000.0],
            "Y1": [8446000.0],
            "X2": [419100.0],
            "Y2": [8446100.0],
        }
    )
    updated = materialize_layer_linestrings(frame)
    geometry = updated.geometry.iloc[0]
    assert geometry.geom_type == "LineString"
    assert geometry.coords[0] == (419000.0, 8446000.0)
    assert geometry.coords[1] == (419100.0, 8446100.0)
    assert updated.crs is not None


def test_materialize_mapped_coordinates_for_line_layer() -> None:
    dataset = GisDataset()
    dataset.add_layer(
        "EQPM_IN110",
        gpd.GeoDataFrame(
            {
                "id0": ["L1"],
                "X1": [419000.0],
                "Y1": [8446000.0],
                "X2": [419100.0],
                "Y2": [8446100.0],
            }
        ),
    )
    dataset.add_layer(
        "NMT_IN110",
        gpd.GeoDataFrame({"ID": ["N1"], "X": [419000.0], "Y": [8446000.0]}),
    )
    mapping = MappingConfig(
        buses=LayerMapping(
            source="NMT_IN110",
            fields={"id": "ID", "x": "X", "y": "Y"},
        ),
        lines=LayerMapping(
            source="EQPM_IN110",
            fields={"id": "id0"},
        ),
    )
    updated = materialize_mapped_coordinates(dataset, mapping)
    line_geometry = updated.layer("EQPM_IN110").geometry.iloc[0]
    assert line_geometry.geom_type == "LineString"
    bus_geometry = updated.layer("NMT_IN110").geometry.iloc[0]
    assert bus_geometry.geom_type == "Point"
