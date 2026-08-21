import pytest

from gis2dgs.powerfactory import (
    DuplicatePowerFactoryObjectError,
    PowerFactoryModel,
    PowerFactoryObject,
    PowerFactoryReference,
)


def test_model_add_and_find_by_class() -> None:
    model = PowerFactoryModel()
    obj = PowerFactoryObject("ElmTerm", "K1", "Bus 1")
    model.add(obj)
    assert model.get("K1") == obj
    assert model.find_by_class("ElmTerm") == (obj,)
    assert model.summary()["objects"] == 1


def test_model_rejects_duplicate_foreign_key() -> None:
    model = PowerFactoryModel()
    model.add(PowerFactoryObject("ElmTerm", "K1", "Bus 1"))
    with pytest.raises(DuplicatePowerFactoryObjectError):
        model.add(PowerFactoryObject("ElmTerm", "K1", "Bus 2"))


def test_reference_rejects_blank_target() -> None:
    with pytest.raises(ValueError):
        PowerFactoryReference(" ")
