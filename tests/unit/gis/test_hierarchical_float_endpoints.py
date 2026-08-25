import geopandas as gpd
import pandas as pd

from gis2dgs.config.models import LayerMapping
from gis2dgs.gis.dataset import GisDataset
from gis2dgs.gis.hierarchical import (
    apply_hierarchical_line_endpoints,
    prepare_hierarchical_connectivity,
)


def test_hierarchical_endpoints_accept_float32_parent_column() -> None:
    lines = gpd.GeoDataFrame(
        {
            "ID": [1, 2],
            "CÓDIGO TRAMO PADRE": pd.Series([0.0, 6616.0], dtype="float32"),
            "ALIMENTADOR": ["F1", "F1"],
            "DISTRITO": ["A", "B"],
        }
    )
    updated = apply_hierarchical_line_endpoints(
        lines,
        line_id_field="ID",
        parent_field="CÓDIGO TRAMO PADRE",
        feeder_field="ALIMENTADOR",
        from_bus_field="CÓDIGO TRAMO PADRE",
        to_bus_field="DISTRITO",
    )
    assert updated.attrs["hierarchical_from_bus_field"] == "from_bus"
    assert updated.attrs["hierarchical_to_bus_field"] == "to_bus"
    assert updated.loc[0, "from_bus"] == "F1"
    assert updated.loc[0, "to_bus"] == "1"
    assert updated.loc[1, "from_bus"] == "6616"
    assert updated.loc[1, "to_bus"] == "2"
    assert updated["CÓDIGO TRAMO PADRE"].dtype == "float32"


def test_prepare_hierarchical_updates_mapping_off_numeric_parent() -> None:
    dataset = GisDataset()
    dataset.add_layer(
        "BD_Tramo AT",
        gpd.GeoDataFrame(
            {
                "ID": [10],
                "CÓDIGO TRAMO PADRE": pd.Series([0.0], dtype="float32"),
                "ALIMENTADOR": ["S1"],
                "DISTRITO": ["X"],
            }
        ),
    )
    dataset.add_layer(
        "BD_SED",
        gpd.GeoDataFrame({"ID": pd.Series([1], dtype="int32"), "V": [13.2]}),
    )
    line_mapping = LayerMapping(
        source="BD_Tramo AT",
        fields={
            "id": "ID",
            "from_bus": "CÓDIGO TRAMO PADRE",
            "to_bus": "DISTRITO",
            "length_km": "ID",
        },
        defaults={"nominal_voltage_kv": 13.2},
    )
    bus_mapping = LayerMapping(
        source="BD_SED",
        fields={"id": "ID", "nominal_voltage_kv": "V"},
        defaults={},
    )
    updated, applied = prepare_hierarchical_connectivity(
        dataset,
        line_layer="BD_Tramo AT",
        bus_layer="BD_SED",
        line_mapping=line_mapping,
        bus_mapping=bus_mapping,
    )
    assert applied
    assert line_mapping.fields["from_bus"] == "from_bus"
    assert line_mapping.fields["to_bus"] == "to_bus"
    assert updated.layer("BD_Tramo AT").loc[0, "from_bus"] == "S1"
    assert "10" in {str(value) for value in updated.layer("BD_SED")["ID"].tolist()}
