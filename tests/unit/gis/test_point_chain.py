import geopandas as gpd
from shapely.geometry import Point

from gis2dgs.gis.point_chain import assign_line_endpoints_from_point_chain


def test_assign_line_endpoints_snaps_to_same_coordinate_nodes() -> None:
    points = gpd.GeoDataFrame(
        {
            "ID": ["P1", "P2", "P3"],
            "LINEA": ["F1", "F1", "F1"],
            "NRO": [1, 2, 3],
            "geometry": [Point(0, 0), Point(100, 0), Point(200, 0)],
        },
        crs="EPSG:32718",
    )
    lines = gpd.GeoDataFrame(
        {
            "ID": ["T1", "T2"],
            "ALIM": ["F1", "F1"],
            "PADRE": [None, "T1"],
            "LONG_M": [100.0, 100.0],
        }
    )
    updated, stats = assign_line_endpoints_from_point_chain(
        lines,
        points,
        line_id_field="ID",
        point_id_field="ID",
        line_key_field="ALIM",
        point_key_field="LINEA",
        sequence_field="NRO",
        parent_field="PADRE",
        length_field="LONG_M",
        length_unit_is_metres=True,
        from_bus_field="from_bus",
        to_bus_field="to_bus",
    )
    assert stats.lines_updated == 2
    assert stats.feeders_linked == 1
    row1 = updated.loc[updated["ID"] == "T1"].iloc[0]
    row2 = updated.loc[updated["ID"] == "T2"].iloc[0]
    assert row1["from_bus"] == "P1"
    assert row1["to_bus"] == "P2"
    assert row2["from_bus"] == "P2"
    assert row2["to_bus"] == "P3"
    assert list(row1.geometry.coords) == [(0.0, 0.0), (100.0, 0.0)]
    assert list(row2.geometry.coords) == [(100.0, 0.0), (200.0, 0.0)]


def test_materialize_geometry_text_points() -> None:
    from gis2dgs.config.models import LayerMapping
    from gis2dgs.gis.coordinates import materialize_layer_points

    frame = gpd.GeoDataFrame(
        {"GEOMETRÍA": ["Nodo:  X- 421677.43  Y- 8453832.776"]}
    )
    mapping = LayerMapping(
        source="structs", fields={"x": "GEOMETRÍA", "y": "GEOMETRÍA"}
    )
    updated = materialize_layer_points(frame, mapping, default_crs="EPSG:32718")
    assert updated.geometry.iloc[0].x == 421677.43
    assert updated.geometry.iloc[0].y == 8453832.776
