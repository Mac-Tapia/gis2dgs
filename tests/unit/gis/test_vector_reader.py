from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

from gis2dgs.gis import VectorFileReader


def test_vector_reader_geojson(tmp_path: Path) -> None:
    path = tmp_path / "nodes.geojson"
    frame = gpd.GeoDataFrame({"id": ["N1"]}, geometry=[Point(-73.2, -3.7)], crs="EPSG:4326")
    frame.to_file(path, driver="GeoJSON")
    dataset = VectorFileReader(path).read()
    assert dataset.names() == ("nodes",)
    assert dataset.layer("nodes").iloc[0]["id"] == "N1"
