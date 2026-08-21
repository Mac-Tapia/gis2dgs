import pytest

from gis2dgs.powerfactory import ForeignKeyFactory


def test_foreign_key_is_deterministic() -> None:
    factory = ForeignKeyFactory("ORG")
    assert factory.make("bus", "B1") == "ORG:bus:B1"
    assert factory.make("bus", "B1") == factory.make("bus", "B1")


def test_foreign_key_unsafe_id_gets_collision_resistant_suffix() -> None:
    factory = ForeignKeyFactory()
    a = factory.make("bus", "A/B")
    b = factory.make("bus", "A B")
    assert a != b
    assert "~" in a and "~" in b


def test_foreign_key_rejects_blank_values() -> None:
    with pytest.raises(ValueError):
        ForeignKeyFactory("")
    with pytest.raises(ValueError):
        ForeignKeyFactory().make("bus", " ")


def test_foreign_key_is_limited_to_powerfactory_recommended_length() -> None:
    factory = ForeignKeyFactory()
    key = factory.make("line", "THIS_IS_A_VERY_LONG_GIS_IDENTIFIER_THAT_EXCEEDS_THE_LIMIT")
    assert len(key) <= 40
    assert "~" in key


def test_long_foreign_keys_remain_deterministic_and_distinct() -> None:
    factory = ForeignKeyFactory()
    a = factory.make("line", "A" * 80 + "1")
    b = factory.make("line", "A" * 80 + "2")
    assert a == factory.make("line", "A" * 80 + "1")
    assert a != b
