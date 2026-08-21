import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from gis2dgs.input import InputDataset, discover_schema


def test_schema_discovery_reports_tabular_and_spatial_metadata() -> None:
    dataset = InputDataset()
    dataset.add_table("table", pd.DataFrame({"id": [1, 2], "value": [1.0, None]}))
    dataset.add_table(
        "geo",
        gpd.GeoDataFrame({"id": ["A"]}, geometry=[Point(0, 0)], crs="EPSG:4326"),
    )

    report = discover_schema(dataset)
    as_dict = report.as_dict()

    assert as_dict["tables"][0]["rows"] == 2
    assert as_dict["tables"][1]["is_spatial"] is True
    assert as_dict["tables"][1]["crs"].upper().endswith("4326")
