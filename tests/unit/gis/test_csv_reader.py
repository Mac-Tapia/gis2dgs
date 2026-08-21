from pathlib import Path

import pytest

from gis2dgs.gis import CsvPointReader, GisSchemaError


def test_csv_point_reader(tmp_path: Path) -> None:
    path = tmp_path / "nodes.csv"
    path.write_text("id,x,y\nN1,-73.2,-3.7\n", encoding="utf-8")
    dataset = CsvPointReader(path, x_column="x", y_column="y", crs="EPSG:4326").read()
    frame = dataset.layer("nodes")
    assert len(frame) == 1
    assert frame.crs is not None


def test_csv_point_reader_requires_xy(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("id,x\nN1,-73.2\n", encoding="utf-8")
    with pytest.raises(GisSchemaError):
        CsvPointReader(path, x_column="x", y_column="y", crs="EPSG:4326").read()
