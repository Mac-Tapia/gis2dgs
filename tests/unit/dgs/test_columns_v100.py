from gis2dgs.dgs import DgsColumnDefinition, DgsColumnType


def test_parse_dgs_text_header() -> None:
    definition = DgsColumnDefinition.parse("ID(a:40)")
    assert definition.name == "ID"
    assert definition.type == DgsColumnType.TEXT
    assert definition.size == 40


def test_parse_dgs_pointer_and_real_headers() -> None:
    assert DgsColumnDefinition.parse("fold_id(p)").type == DgsColumnType.POINTER
    assert DgsColumnDefinition.parse("uknom(r)").type == DgsColumnType.REAL
    assert DgsColumnDefinition.parse("iUsage(i)").type == DgsColumnType.INTEGER
