import pandas as pd

from gis2dgs.input import InputDataset, discover_schema
from gis2dgs.input.compact import compact_frame
from gis2dgs.input.readers.csv import CsvInputReader


def test_copy_frame_false_keeps_same_object() -> None:
    frame = pd.DataFrame({"id": [1, 2, 3]})
    dataset = InputDataset()
    dataset.add_table("nodes", frame, copy_frame=False)
    assert dataset.table("nodes").frame is frame


def test_discover_schema_sample_rows_keeps_full_row_count() -> None:
    dataset = InputDataset()
    dataset.add_table("table", pd.DataFrame({"id": list(range(20)), "value": list(range(20))}))
    report = discover_schema(dataset, sample_rows=5)
    assert report.tables[0].rows == 20
    assert report.tables[0].columns[0].unique_count == 5


def test_csv_reader_sample_rows(tmp_path) -> None:
    path = tmp_path / "nodes.csv"
    rows = "id,kv\n" + "\n".join(f"B{index},{index}" for index in range(12))
    path.write_text(rows, encoding="utf-8")
    data = CsvInputReader(path, sample_rows=4, compact=False).read()
    assert len(data.table("nodes").frame) == 4


def test_compact_frame_downcasts_integers() -> None:
    frame = pd.DataFrame({"id": [1, 2, 3]})
    compacted = compact_frame(frame, copy=True)
    assert compacted["id"].dtype != object
    assert list(compacted["id"]) == [1, 2, 3]
