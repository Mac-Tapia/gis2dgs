import geopandas as gpd
from shapely.geometry import Point
from sqlalchemy import create_engine

from gis2dgs.gis import PostGisReader


def test_postgis_reader_uses_configured_queries(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    expected = gpd.GeoDataFrame(
        {"id": ["N1"]},
        geometry=[Point(-73.2, -3.7)],
        crs="EPSG:4326",
    )

    def fake_read_postgis(query, engine, geom_col):  # type: ignore[no-untyped-def]
        assert query == "SELECT * FROM nodes"
        assert geom_col == "geometry"
        return expected

    monkeypatch.setattr(gpd, "read_postgis", fake_read_postgis)
    engine = create_engine("sqlite://")
    dataset = PostGisReader(engine, {"nodes": "SELECT * FROM nodes"}).read()
    assert dataset.layer("nodes").iloc[0]["id"] == "N1"
