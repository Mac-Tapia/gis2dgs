import geopandas as gpd

from gis2dgs.gis.geodataframe_utils import safe_frame_crs


def test_safe_frame_crs_without_active_geometry() -> None:
    frame = gpd.GeoDataFrame({"id": ["A"]})
    assert safe_frame_crs(frame) is None
