import pandas as pd
import pytest

from gis2dgs.input import DatasetConflictError, InputDataset, merge_datasets


def test_input_dataset_merges_independent_tables() -> None:
    left = InputDataset()
    left.add_table("buses", pd.DataFrame({"id": [1]}), source_id="a")
    right = InputDataset()
    right.add_table("lines", pd.DataFrame({"id": [2]}), source_id="b")

    merged = merge_datasets([left, right])

    assert merged.names() == ("buses", "lines")
    assert merged.table("buses").source_id == "a"


def test_input_dataset_rejects_duplicate_table_by_default() -> None:
    left = InputDataset()
    left.add_table("buses", pd.DataFrame({"id": [1]}))
    right = InputDataset()
    right.add_table("buses", pd.DataFrame({"id": [2]}))

    with pytest.raises(DatasetConflictError):
        merge_datasets([left, right])


def test_plain_frames_bridge_to_phase3_gis_dataset() -> None:
    data = InputDataset()
    data.add_table("buses", pd.DataFrame({"id": ["B1"]}))
    bridged = data.to_gis_dataset()
    assert bridged.names() == ("buses",)
    assert bridged.layer("buses").iloc[0]["id"] == "B1"
