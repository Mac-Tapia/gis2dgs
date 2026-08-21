import geopandas as gpd

from gis2dgs.config.models import LayerMapping
from gis2dgs.gis.dataset import GisDataset
from gis2dgs.gis.hierarchical import (
    apply_hierarchical_line_endpoints,
    detect_feeder_column,
    detect_parent_column,
    prepare_hierarchical_connectivity,
    synthesize_endpoint_buses,
)


def test_detect_parent_and_feeder_columns() -> None:
    columns = ["CodTramoBT", "CodTramoBTPadre", "CodSalidaBT", "Longitud"]
    assert detect_parent_column(columns) == "CodTramoBTPadre"
    assert detect_feeder_column(columns) == "CodSalidaBT"


def test_apply_hierarchical_line_endpoints_uses_feeder_for_root_parent() -> None:
    lines = gpd.GeoDataFrame(
        {
            "CodTramoBT": ["L1", "L2"],
            "CodTramoBTPadre": ["0", "L1"],
            "CodSalidaBT": ["S1", "S1"],
        }
    )
    updated = apply_hierarchical_line_endpoints(
        lines,
        line_id_field="CodTramoBT",
        parent_field="CodTramoBTPadre",
        feeder_field="CodSalidaBT",
    )
    assert updated.loc[0, "from_bus"] == "S1"
    assert updated.loc[0, "to_bus"] == "L1"
    assert updated.loc[1, "from_bus"] == "L1"
    assert updated.loc[1, "to_bus"] == "L2"


def test_synthesize_endpoint_buses_appends_missing_ids() -> None:
    buses = gpd.GeoDataFrame({"CodNodoMT": ["B1"], "UTMEste": [1.0], "UTMNorte": [2.0]})
    lines = gpd.GeoDataFrame({"from_bus": ["B1", "B2"], "to_bus": ["B2", "B3"]})
    bus_mapping = LayerMapping(
        source="buses",
        fields={"id": "CodNodoMT", "x": "UTMEste", "y": "UTMNorte"},
        defaults={"nominal_voltage_kv": 0.4},
    )
    updated = synthesize_endpoint_buses(
        buses,
        lines,
        bus_mapping=bus_mapping,
        bus_id_field="CodNodoMT",
        from_bus_field="from_bus",
        to_bus_field="to_bus",
    )
    assert set(updated["CodNodoMT"].tolist()) == {"B1", "B2", "B3"}


def test_prepare_hierarchical_connectivity_updates_dataset_and_mapping() -> None:
    dataset = GisDataset()
    dataset.add_layer(
        "btTramo",
        gpd.GeoDataFrame(
            {
                "CodTramoBT": ["L1"],
                "CodTramoBTPadre": ["0"],
                "CodSalidaBT": ["S1"],
                "Longitud": [1.0],
            }
        ),
    )
    dataset.add_layer(
        "mtNodoEnlace",
        gpd.GeoDataFrame({"CodNodoMT": ["B1"], "UTMEste": [1.0], "UTMNorte": [2.0]}),
    )
    line_mapping = LayerMapping(
        source="btTramo",
        fields={"id": "CodTramoBT", "length_km": "Longitud"},
        defaults={"nominal_voltage_kv": 0.4},
    )
    bus_mapping = LayerMapping(
        source="mtNodoEnlace",
        fields={"id": "CodNodoMT", "x": "UTMEste", "y": "UTMNorte"},
        defaults={"nominal_voltage_kv": 0.4},
    )
    updated, applied = prepare_hierarchical_connectivity(
        dataset,
        line_layer="btTramo",
        bus_layer="mtNodoEnlace",
        line_mapping=line_mapping,
        bus_mapping=bus_mapping,
    )
    assert applied is True
    lines = updated.layer("btTramo")
    assert lines.loc[0, "from_bus"] == "S1"
    assert lines.loc[0, "to_bus"] == "L1"
    assert "S1" in set(updated.layer("mtNodoEnlace")["CodNodoMT"].tolist())
    assert line_mapping.fields["from_bus"] == "from_bus"
    assert line_mapping.fields["to_bus"] == "to_bus"
