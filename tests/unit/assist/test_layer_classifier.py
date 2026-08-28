from gis2dgs.assist.layer_classifier import classify_dataset_layers
from gis2dgs.input.schema.discovery import ColumnSchema, TableSchema


def _column(name: str, dtype: str = "str", unique: int = 100) -> ColumnSchema:
    return ColumnSchema(
        name=name,
        dtype=dtype,
        nullable=False,
        non_null_count=unique,
        unique_count=unique,
    )


def test_classifies_igea_excel_trio_by_schema_signature() -> None:
    tables = (
        TableSchema(
            "NMT_IN110",
            260,
            (
                _column("ID", unique=260),
                _column("X", "float64", 260),
                _column("Y", "float64", 260),
            ),
            False,
            None,
            None,
            None,
        ),
        TableSchema(
            "EQPM_IN110",
            134,
            (
                _column("id0", unique=134),
                _column("X1", "float64", 134),
                _column("Y1", "float64", 134),
                _column("X2", "float64", 134),
                _column("Y2", "float64", 134),
            ),
            False,
            None,
            None,
            None,
        ),
        TableSchema(
            "AMT_IN110",
            1,
            (
                _column("id0", unique=1),
                _column("nominal_9", "int8", 1),
                _column("X1", "float64", 1),
                _column("Y1", "float64", 1),
            ),
            False,
            None,
            None,
            None,
        ),
    )
    report = classify_dataset_layers(tables)
    roles = {item.table: item.role for item in report.tables}
    assert roles["NMT_IN110"] == "buses"
    assert roles["EQPM_IN110"] == "lines"
    assert roles["AMT_IN110"] == "sources"
