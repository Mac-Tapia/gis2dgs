import pytest

from gis2dgs.electrical import (
    DuplicateElectricalTypeError,
    ElectricalLibrary,
    LineType,
    TransformerType,
    UnknownElectricalTypeError,
)


def _line_type(type_id: str = "LT1") -> LineType:
    return LineType(type_id, "Line type", 10.0, 0.4, 0.3, 200.0)


def _transformer_type(type_id: str = "TT1") -> TransformerType:
    return TransformerType(
        type_id,
        "Transformer type",
        1.0,
        10.0,
        0.4,
        6.0,
        10.0,
        2.0,
        1.0,
        "Dyn11",
    )


def test_library_add_get_and_summary() -> None:
    library = ElectricalLibrary.from_types(
        line_types=[_line_type()],
        transformer_types=[_transformer_type()],
    )
    assert library.get_line_type("LT1").name == "Line type"
    assert library.get_transformer_type("TT1").name == "Transformer type"
    assert library.summary() == {
        "line_types": 1,
        "transformer_types": 1,
        "total_types": 2,
    }


def test_library_rejects_duplicate_type() -> None:
    library = ElectricalLibrary()
    library.add_line_type(_line_type())
    with pytest.raises(DuplicateElectricalTypeError):
        library.add_line_type(_line_type())


def test_library_get_unknown_type_raises_specific_error() -> None:
    library = ElectricalLibrary()
    with pytest.raises(UnknownElectricalTypeError):
        library.get_transformer_type("MISSING")


def test_library_empty_and_find_methods() -> None:
    library = ElectricalLibrary()
    assert library.is_empty
    assert library.find_line_type("MISSING") is None
    assert library.find_transformer_type("MISSING") is None
    with pytest.raises(UnknownElectricalTypeError):
        library.get_line_type("MISSING")


def test_library_rejects_inconsistent_dictionary_key() -> None:
    with pytest.raises(ValueError, match="does not match object ID"):
        ElectricalLibrary(line_types={"WRONG": _line_type("LT1")})


def test_library_rejects_duplicate_transformer_type() -> None:
    library = ElectricalLibrary()
    library.add_transformer_type(_transformer_type())
    with pytest.raises(DuplicateElectricalTypeError):
        library.add_transformer_type(_transformer_type())
