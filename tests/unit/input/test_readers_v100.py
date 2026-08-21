from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from gis2dgs.input.readers import (
    CsvInputReader,
    ExcelInputReader,
    SqlAlchemyInputReader,
    VectorInputReader,
)


def test_csv_reader(tmp_path: Path) -> None:
    path = tmp_path / "nodes.csv"
    path.write_text("id,kv\nB1,10\n", encoding="utf-8")
    data = CsvInputReader(path, table_name="buses").read()
    assert data.names() == ("buses",)
    assert data.table("buses").frame.iloc[0]["id"] == "B1"


def test_excel_reader_reads_all_sheets(tmp_path: Path) -> None:
    path = tmp_path / "network.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"id": ["B1"]}).to_excel(writer, sheet_name="NODES", index=False)
        pd.DataFrame({"id": ["L1"]}).to_excel(writer, sheet_name="LINES", index=False)
    data = ExcelInputReader(path, aliases={"NODES": "buses", "LINES": "lines"}).read()
    assert data.names() == ("buses", "lines")


def test_vector_reader_reads_geojson(tmp_path: Path) -> None:
    path = tmp_path / "nodes.geojson"
    frame = gpd.GeoDataFrame({"id": ["B1"]}, geometry=[Point(1, 2)], crs="EPSG:4326")
    frame.to_file(path, driver="GeoJSON")
    data = VectorInputReader(path).read()
    table = data.table("nodes")
    assert isinstance(table.frame, gpd.GeoDataFrame)
    assert table.frame.crs.to_epsg() == 4326


def test_sqlalchemy_reader_reads_sqlite(tmp_path: Path) -> None:
    db = tmp_path / "network.sqlite"
    uri = f"sqlite:///{db}"
    from sqlalchemy import create_engine

    engine = create_engine(uri)
    pd.DataFrame({"id": ["B1"], "kv": [10.0]}).to_sql("nodes", engine, index=False)
    engine.dispose()

    data = SqlAlchemyInputReader(db, tables=("nodes",), aliases={"nodes": "buses"}).read()
    assert data.names() == ("buses",)
    assert data.table("buses").frame.iloc[0]["kv"] == 10.0


def test_sqlalchemy_reader_supports_configured_spatial_queries(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "network.sqlite"
    uri = f"sqlite:///{db}"
    from sqlalchemy import create_engine

    engine = create_engine(uri)
    pd.DataFrame({"id": [1]}).to_sql("dummy", engine, index=False)
    engine.dispose()

    expected = gpd.GeoDataFrame(
        {"id": ["B1"]}, geometry=[Point(0, 0)], crs="EPSG:4326"
    )

    def fake_read_postgis(sql, connection, geom_col):
        assert sql == "SELECT * FROM spatial_nodes"
        assert geom_col == "geometry"
        return expected

    monkeypatch.setattr(gpd, "read_postgis", fake_read_postgis)
    data = SqlAlchemyInputReader(
        db,
        tables=(),
        spatial_queries={"nodes": "SELECT * FROM spatial_nodes"},
    ).read()

    assert isinstance(data.table("nodes").frame, gpd.GeoDataFrame)
