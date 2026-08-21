import pandas as pd

from gis2dgs.config.models import LayerMapping
from gis2dgs.gis.mapping.accessor import RowAccessor
from gis2dgs.gis.mapping.domain_mapper import GisToDomainMapper


def test_build_source_skips_rows_without_operational_name() -> None:
    mapping = LayerMapping(
        source="mtSalida",
        fields={"id": "CodSalidaMT", "name": "EtiquetaSalida", "bus_id": "CodSalidaMT"},
        defaults={"nominal_voltage_kv": 10.0},
        units={"nominal_voltage_kv": "kV"},
    )
    mapper = GisToDomainMapper.__new__(GisToDomainMapper)
    mapper.config = None  # type: ignore[assignment]
    mapper.voltage_lookup = None

    placeholder = RowAccessor(
        "mtSalida",
        0,
        pd.Series({"CodSalidaMT": "L1", "EtiquetaSalida": float("nan")}),
        mapping,
    )
    assert mapper._build_source(placeholder) is None

    real = RowAccessor(
        "mtSalida",
        1,
        pd.Series({"CodSalidaMT": "L14231", "EtiquetaSalida": "0101"}),
        mapping,
    )
    source = mapper._build_source(real)
    assert source is not None
    assert source.name == "0101"
