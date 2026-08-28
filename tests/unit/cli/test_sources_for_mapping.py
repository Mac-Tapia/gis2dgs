from pathlib import Path

from gis2dgs.cli.workspace import _mapped_table_names, _sources_for_paths


def test_mapped_table_names_extracts_entity_sources() -> None:
    mapping = {
        "buses": {"source": "BD_SED", "fields": {"id": "ID"}},
        "lines": {"source": "BD_Tramo BT", "fields": {"id": "ID"}},
        "target_crs": None,
        "connectivity": {"apply_unambiguous": True},
    }
    assert _mapped_table_names(mapping) == {"BD_SED", "BD_Tramo BT"}


def test_sources_for_paths_keeps_every_loaded_file(tmp_path: Path) -> None:
    kept = tmp_path / "BD_SED.xlsx"
    other = tmp_path / "BD_Acometidas.xlsx"
    kept.write_bytes(b"pk")
    other.write_bytes(b"pk")
    mapping = {"buses": {"source": "BD_SED", "fields": {"id": "ID"}}}
    sources = _sources_for_paths((kept, other), mapping=mapping)
    names = {(item.get("options") or {}).get("table_name") for item in sources}
    assert names == {"BD_SED", "BD_Acometidas"}
