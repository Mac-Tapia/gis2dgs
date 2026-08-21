import geopandas as gpd

from gis2dgs.gis.dataset import GisDataset
from gis2dgs.gis.normalizer import convert_voltage_to_kv
from gis2dgs.gis.voltage_lookup import VoltageLookup, detect_voltage_lookup


def test_detect_voltage_lookup_from_tensiones_table() -> None:
    dataset = GisDataset()
    dataset.add_layer(
        "Tensiones",
        gpd.GeoDataFrame({"CodTenNomi": ["G", "D"], "Tension": [22.9, 10.0]}),
    )
    lookup = detect_voltage_lookup(dataset)
    assert lookup is not None
    assert lookup.by_code["G"] == 22.9
    assert lookup.by_code["D"] == 10.0


def test_convert_voltage_to_kv_resolves_lookup_codes() -> None:
    codes = {"G": 22.9, "D": 10.0}
    assert convert_voltage_to_kv("G", "kV", code_lookup=codes) == 22.9
    assert convert_voltage_to_kv(13.2, "kV", code_lookup=codes) == 13.2


def test_voltage_lookup_resolve_falls_back_to_numeric_values() -> None:
    lookup = VoltageLookup("Tensiones", "CodTenNomi", "Tension", {"G": 22.9})
    assert lookup.resolve("G") == 22.9
    assert lookup.resolve(13.2) == 13.2
