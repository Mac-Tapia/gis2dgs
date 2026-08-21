import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from gis2dgs.gis import PostGisReader

pytestmark = pytest.mark.postgis


def test_real_postgis_reader_roundtrip() -> None:
    url = os.getenv("GIS2DGS_POSTGIS_TEST_URL")
    if not url:
        pytest.skip("GIS2DGS_POSTGIS_TEST_URL is not configured.")

    engine = create_engine(url, pool_pre_ping=True)
    table_name = f"gis2dgs_it_{uuid4().hex}"

    try:
        with engine.begin() as connection:
            version = connection.execute(text("SELECT PostGIS_Version()"))
            assert version.scalar_one()

            connection.execute(
                text(
                    f'CREATE TEMP TABLE "{table_name}" ('
                    "id text PRIMARY KEY, "
                    "geometry geometry(Point, 4326) NOT NULL)"
                )
            )
            connection.execute(
                text(
                    f'INSERT INTO "{table_name}" (id, geometry) '
                    "VALUES (:id, ST_SetSRID(ST_MakePoint(:x, :y), 4326))"
                ),
                {"id": "N1", "x": -73.25, "y": -3.74},
            )

            dataset = PostGisReader(
                connection,
                {"nodes": f'SELECT id, geometry FROM "{table_name}"'},
            ).read()

        frame = dataset.layer("nodes")
        assert list(frame["id"]) == ["N1"]
        assert frame.crs is not None
        assert frame.geometry.iloc[0].x == pytest.approx(-73.25)
        assert frame.geometry.iloc[0].y == pytest.approx(-3.74)
    finally:
        engine.dispose()
