import geopandas as gpd
import pytest
from shapely.geometry import Point

from gis2dgs.gis.dataset import GisDataset
from gis2dgs.gis.exceptions import GisLayerNotFoundError


def test_dataset_add_and_get_layer() -> None:
    dataset = GisDataset()
    frame = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    dataset.add_layer("nodes", frame)

    assert dataset.names() == ("nodes",)
    assert len(dataset.layer("nodes")) == 1


def test_dataset_returns_copies_on_add() -> None:
    dataset = GisDataset()
    frame = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    dataset.add_layer("nodes", frame)
    frame.loc[0, "id"] = 999

    assert dataset.layer("nodes").loc[0, "id"] == 1


def test_missing_layer_has_domain_specific_error() -> None:
    with pytest.raises(GisLayerNotFoundError):
        GisDataset().layer("missing")


def test_dataset_reprojects_without_mutating_original() -> None:
    dataset = GisDataset()
    frame = gpd.GeoDataFrame(
        {"id": [1]},
        geometry=[Point(-77.0, -12.0)],
        crs="EPSG:4326",
    )
    dataset.add_layer("nodes", frame)

    projected = dataset.reprojected("EPSG:3857")

    assert str(dataset.layer("nodes").crs) == "EPSG:4326"
    assert str(projected.layer("nodes").crs) == "EPSG:3857"
    assert projected.layer("nodes").geometry.iloc[0].x != pytest.approx(-77.0)


def test_reprojection_rejects_missing_source_crs() -> None:
    dataset = GisDataset()
    frame = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(0, 0)])
    dataset.add_layer("nodes", frame)

    with pytest.raises(ValueError, match="has no CRS"):
        dataset.reprojected("EPSG:4326")
