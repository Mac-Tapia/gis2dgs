from pathlib import Path

from gis2dgs.input.dgs_relevance import (
    filter_dgs_relevant_paths,
    is_dgs_relevant_tabular_file,
)


def test_skips_non_electrical_inventory_layers(tmp_path: Path) -> None:
    names = [
        "BD_Tramo de Vía.xlsx",
        "BD_Zona de Concesión.xlsx",
        "BD_Retenida.xlsx",
        "BD_PAT.xlsx",
        "BD_Pararrayos.xlsx",
        "BD_Estructuras AT.xlsx",
        "BD_UAP.xlsx",
    ]
    paths = []
    for name in names:
        path = tmp_path / name
        path.write_bytes(b"pk")
        paths.append(path)
        assert is_dgs_relevant_tabular_file(path) is False

    included, decisions = filter_dgs_relevant_paths(paths)
    assert included == ()
    assert all(not item.include for item in decisions)


def test_keeps_electrical_layers_and_dedupes_dated_copies(tmp_path: Path) -> None:
    keep = [
        "BD_Tramo BT.xlsx",
        "BD_SED.xlsx",
        "BD_SED_15.01.2025.xlsx",
        "BD_Salida MT.xlsx",
        "BD_Transformador Distribución.xlsx",
        "BD_SET.xlsx",
        "BD_Suministros.xlsx",
        "BD_Suministros_25.05.2026.xlsx",
    ]
    skip = ["BD_Tramo de Vía.xlsx", "BD_PAT.xlsx"]
    paths = []
    for name in keep + skip:
        path = tmp_path / name
        path.write_bytes(b"pk")
        paths.append(path)

    included, decisions = filter_dgs_relevant_paths(paths)
    names = {path.name for path in included}
    assert "BD_Tramo BT.xlsx" in names
    assert "BD_SED.xlsx" in names
    assert "BD_SED_15.01.2025.xlsx" not in names
    assert "BD_Suministros.xlsx" in names
    assert "BD_Suministros_25.05.2026.xlsx" not in names
    assert "BD_Tramo de Vía.xlsx" not in names
    assert "BD_PAT.xlsx" not in names
    assert any("duplicado" in item.reason for item in decisions if not item.include)


def test_keeps_english_canonical_layer_names(tmp_path: Path) -> None:
    for name in ("buses.csv", "lines.csv", "loads.csv", "sources.csv"):
        path = tmp_path / name
        path.write_text("id\n1\n", encoding="utf-8")
        assert is_dgs_relevant_tabular_file(path) is True


def test_igea_feeder_excel_layers_are_electrical(tmp_path: Path) -> None:
    for name in ("AMT_IN110.xlsx", "EQPM_IN110.xlsx", "NMT_IN110.xlsx"):
        path = tmp_path / name
        path.write_bytes(b"pk")
        assert is_dgs_relevant_tabular_file(path) is True


def test_filter_includes_unknown_tabular_names(tmp_path: Path) -> None:
    path = tmp_path / "custom_network_layer.csv"
    path.write_text("id\n1\n", encoding="utf-8")
    included, decisions = filter_dgs_relevant_paths([path])
    assert included == (path,)
    assert decisions[0].include is True
