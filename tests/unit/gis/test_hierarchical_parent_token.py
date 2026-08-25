import geopandas as gpd

from gis2dgs.gis.hierarchical import (
    _parent_identifier,
    apply_hierarchical_line_endpoints,
    detect_parent_column,
)


def test_parent_identifier_strips_inventory_label() -> None:
    assert _parent_identifier("977870 - AS035116") == "977870"
    assert _parent_identifier(977870) == "977870"


def test_detect_codigo_tramo_padre() -> None:
    assert (
        detect_parent_column(["CODIGO", "CÓDIGO TRAMO PADRE", "LONGITUD REAL (m)"])
        == "CÓDIGO TRAMO PADRE"
    )


def test_hierarchical_endpoints_use_numeric_parent_token() -> None:
    lines = gpd.GeoDataFrame(
        {
            "CODIGO": [977871, 977870],
            "CÓDIGO TRAMO PADRE": ["977870 - AS035116", "0"],
            "SALIDA SED": ["C1", "C1"],
        }
    )
    result = apply_hierarchical_line_endpoints(
        lines,
        line_id_field="CODIGO",
        parent_field="CÓDIGO TRAMO PADRE",
        feeder_field="SALIDA SED",
    )
    assert result.loc[0, "from_bus"] == "977870"
    assert result.loc[0, "to_bus"] == "977871"
    assert result.loc[1, "from_bus"] == "C1"
    assert result.loc[1, "to_bus"] == "977870"


def test_hierarchical_endpoints_redirect_float_parent_and_district() -> None:
    """Compact float32 parent + district to_bus must not raise TypeError on write."""

    import pandas as pd

    lines = gpd.GeoDataFrame(
        {
            "ID": pd.Series([100, 200], dtype="int32"),
            "CÓDIGO TRAMO PADRE": pd.Series([0.0, 100.0], dtype="float32"),
            "DISTRITO": pd.Series([1.0, 2.0], dtype="float32"),
            "SALIDA": ["S1", "S1"],
        }
    )
    result = apply_hierarchical_line_endpoints(
        lines,
        line_id_field="ID",
        parent_field="CÓDIGO TRAMO PADRE",
        feeder_field="SALIDA",
        from_bus_field="CÓDIGO TRAMO PADRE",
        to_bus_field="DISTRITO",
    )
    assert result.attrs["hierarchical_from_bus_field"] == "from_bus"
    assert result.attrs["hierarchical_to_bus_field"] == "to_bus"
    assert result.loc[0, "from_bus"] == "S1"
    assert result.loc[0, "to_bus"] == "100"
    assert result.loc[1, "from_bus"] == "100"
    assert result.loc[1, "to_bus"] == "200"
    assert str(result["CÓDIGO TRAMO PADRE"].dtype) == "float32"
