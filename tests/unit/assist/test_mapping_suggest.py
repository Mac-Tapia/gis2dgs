import pandas as pd

from gis2dgs.assist.llm import refine_mapping_with_llm
from gis2dgs.assist.scoring import lexical_score, normalize_token
from gis2dgs.assist.service import suggest_mapping
from gis2dgs.assist.topsis import topsis_select
from gis2dgs.input import InputDataset, discover_schema
from gis2dgs.input.schema.discovery import ColumnSchema, DatasetSchema, TableSchema


def test_normalize_and_lexical_score() -> None:
    assert normalize_token("Tensión_kV") == "tensionkv"
    assert lexical_score("nodo_i", ("from_bus", "nodo_i", "bus1")) == 1.0
    assert lexical_score("voltage_kv", ("nominal_voltage_kv", "tension", "voltage_kv")) >= 0.9
    assert lexical_score("id", ("id", "codigo")) > lexical_score("id_zona", ("id", "codigo"))
    assert lexical_score("mtNodoEnlace", ("nodo", "nodos", "nodoenlace")) >= 0.70
    assert lexical_score("CodNodoMT", ("cod_nodo", "codnodo", "id")) >= 0.85
    assert lexical_score("CodTenNomi", ("codtennomi", "tension", "tennomi")) >= 0.95


def test_type_id_column_prefers_conductor_norm_over_network_type() -> None:
    from gis2dgs.assist.catalog import ENTITIES
    from gis2dgs.assist.service import _column_match_score
    from gis2dgs.input.schema.discovery import ColumnSchema

    type_spec = next(
        field
        for entity in ENTITIES
        if entity.name == "lines"
        for field in entity.fields
        if field.name == "type_id"
    )
    network_type = ColumnSchema("CodTipoRed", "str", False, 100, 2)
    conductor = ColumnSchema("CodNormaFase", "str", False, 100, 50)
    assert _column_match_score(type_spec, conductor) > _column_match_score(
        type_spec, network_type
    )


def test_topsis_selects_balanced_alternative() -> None:
    objectives = [
        (1.0, 0.1, 0.1, 0.1),
        (0.8, 0.8, 0.8, 0.8),
        (0.2, 1.0, 1.0, 1.0),
    ]
    assert topsis_select(objectives, (0.4, 0.25, 0.2, 0.15)) == 1


def test_suggest_mapping_on_spanish_schema() -> None:
    dataset = InputDataset()
    dataset.add_table(
        "nodos",
        pd.DataFrame({"codigo": ["B1", "B2"], "nombre": ["A", "B"], "tension": [13.2, 13.2]}),
    )
    dataset.add_table(
        "tramos",
        pd.DataFrame(
            {
                "codigo": ["L1"],
                "nodo_i": ["B1"],
                "nodo_f": ["B2"],
                "longitud": [1.2],
                "tension": [13.2],
            }
        ),
    )
    dataset.add_table(
        "cargas",
        pd.DataFrame({"codigo": ["C1"], "nodo": ["B2"], "potencia": [0.5], "q": [0.1]}),
    )
    dataset.add_table(
        "alimentadores",
        pd.DataFrame({"codigo": ["S1"], "nodo": ["B1"], "tension": [13.2]}),
    )
    suggestion = suggest_mapping(
        discover_schema(dataset), seed=1, population_size=16, generations=8
    )
    assert suggestion.mapping.buses is not None
    assert suggestion.mapping.buses.source == "nodos"
    assert suggestion.mapping.buses.fields["id"] == "codigo"
    assert suggestion.mapping.buses.fields["nominal_voltage_kv"] == "tension"
    assert suggestion.mapping.lines is not None
    assert suggestion.mapping.lines.source == "tramos"
    assert suggestion.mapping.lines.fields["from_bus"] == "nodo_i"
    assert suggestion.mapping.loads is not None
    assert suggestion.mapping.sources is not None
    assert suggestion.report["pareto_size"] >= 1
    assert suggestion.report["method"] == "nsga-ii+topsis"


def test_llm_skipped_without_credentials(monkeypatch) -> None:
    monkeypatch.delenv("GIS2DGS_LLM_URL", raising=False)
    monkeypatch.delenv("GIS2DGS_LLM_API_KEY", raising=False)
    assert refine_mapping_with_llm({"tables": []}, {}) is None


def test_suggest_mapping_use_llm_without_url_is_fail_open(monkeypatch) -> None:
    monkeypatch.delenv("GIS2DGS_LLM_URL", raising=False)
    monkeypatch.delenv("GIS2DGS_LLM_API_KEY", raising=False)
    dataset = InputDataset()
    dataset.add_table(
        "buses",
        pd.DataFrame({"id": ["B1"], "voltage_kv": [10.0]}),
    )
    dataset.add_table(
        "lines",
        pd.DataFrame(
            {
                "id": ["L1"],
                "from_bus": ["B1"],
                "to_bus": ["B1"],
                "length_km": [0.2],
                "voltage_kv": [10.0],
            }
        ),
    )
    suggestion = suggest_mapping(
        discover_schema(dataset),
        seed=2,
        population_size=12,
        generations=6,
        use_llm=True,
    )
    assert suggestion.mapping.buses is not None
    assert suggestion.mapping.buses.fields["id"] == "id"
    assert suggestion.mapping.lines is not None


def test_suggest_mapping_on_minimal_english_schema() -> None:
    dataset = InputDataset()
    dataset.add_table(
        "buses",
        pd.DataFrame({"id": ["B1", "B2"], "name": ["A", "B"], "voltage_kv": [10.0, 10.0]}),
    )
    dataset.add_table(
        "lines",
        pd.DataFrame(
            {
                "id": ["L1"],
                "from_bus": ["B1"],
                "to_bus": ["B2"],
                "length_km": [1.25],
                "voltage_kv": [10.0],
            }
        ),
    )
    dataset.add_table(
        "loads",
        pd.DataFrame({"id": ["LD1"], "bus_id": ["B2"], "p_mw": [0.8], "q_mvar": [0.25]}),
    )
    dataset.add_table(
        "sources",
        pd.DataFrame({"id": ["SRC1"], "bus_id": ["B1"], "voltage_kv": [10.0]}),
    )
    suggestion = suggest_mapping(
        discover_schema(dataset), seed=42, population_size=16, generations=8
    )
    assert suggestion.mapping.buses is not None
    assert suggestion.mapping.buses.source == "buses"
    assert suggestion.mapping.buses.fields["nominal_voltage_kv"] == "voltage_kv"
    assert suggestion.mapping.lines is not None
    assert suggestion.mapping.lines.fields["from_bus"] == "from_bus"
    assert suggestion.mapping.loads is not None
    assert suggestion.mapping.sources is not None


def test_suggest_mapping_prefers_feeder_table_and_exact_columns() -> None:
    dataset = InputDataset()
    dataset.add_table(
        "M_ALIMENTAD",
        pd.DataFrame(
            {
                "id": [1],
                "codigo": ["AL01"],
                "id_zona": ["Z1"],
                "codset": ["SE1"],
                "codali": [12],
                "tension": ["13.2"],
                "conexionn": ["B1"],
                "aniopes": [2024],
                "resistivid": ["0.1"],
            }
        ),
    )
    suggestion = suggest_mapping(
        discover_schema(dataset), seed=3, population_size=16, generations=8
    )
    assert suggestion.mapping.lines is None
    assert suggestion.mapping.sources is not None
    assert suggestion.mapping.sources.fields["id"] in {"id", "codigo"}
    assert suggestion.mapping.sources.fields["id"] != "id_zona"
    assert suggestion.mapping.sources.fields["bus_id"] == "conexionn"
    assert suggestion.mapping.sources.fields["nominal_voltage_kv"] == "tension"


def _column(name: str, dtype: str = "str", unique: int = 100) -> ColumnSchema:
    return ColumnSchema(name, dtype, False, 100, unique)


def test_suggest_mapping_on_vnr_style_schema() -> None:
    schema = DatasetSchema(
        tables=(
            TableSchema(
                "mtNodoEnlace",
                100,
                (
                    _column("CodNodoMT", unique=100),
                    _column("CodTramoMT", unique=90),
                    _column("UTMEste", "float64", 100),
                    _column("UTMNorte", "float64", 100),
                ),
                False,
                None,
                None,
                None,
            ),
            TableSchema(
                "mtTramo",
                100,
                (
                    _column("CodTramoMT", unique=100),
                    _column("Longitud", "float32", 50),
                    _column("CodTenNomi", unique=3),
                    _column("CodSalidaMT", unique=10),
                ),
                False,
                None,
                None,
                None,
            ),
            TableSchema(
                "Tensiones",
                16,
                (
                    _column("CodTenNomi", unique=16),
                    _column("Tension", "float32", 16),
                ),
                False,
                None,
                None,
                None,
            ),
        )
    )
    suggestion = suggest_mapping(schema, seed=7, population_size=16, generations=8)
    assert suggestion.mapping.buses is not None
    assert suggestion.mapping.buses.source == "mtNodoEnlace"
    assert suggestion.mapping.buses.fields["id"] == "CodNodoMT"
    assert suggestion.mapping.buses.fields.get("x") == "UTMEste"
    assert suggestion.mapping.buses.defaults.get("nominal_voltage_kv") == 1.0
    assert suggestion.mapping.lines is not None
    assert suggestion.mapping.lines.source == "mtTramo"
    assert suggestion.mapping.lines.fields["id"] == "CodTramoMT"
    assert suggestion.mapping.lines.fields["length_km"] == "Longitud"
    assert "from_bus" not in suggestion.mapping.lines.fields
    assert any("connectivity" in warning.lower() for warning in suggestion.report["warnings"])


def test_suggest_mapping_does_not_use_parent_column_as_line_name() -> None:
    schema = DatasetSchema(
        tables=(
            TableSchema(
                "btTramo",
                100,
                (
                    _column("CodTramoBT", unique=100),
                    _column("CodTramoBTPadre", unique=80),
                    _column("CodSalidaBT", unique=20),
                    _column("Longitud", "float32", 50),
                    _column("CodNormaFase", unique=5),
                ),
                False,
                None,
                None,
                None,
            ),
        )
    )
    suggestion = suggest_mapping(schema, seed=11, population_size=16, generations=8)

    assert suggestion.mapping.lines is not None
    assert suggestion.mapping.lines.fields["id"] == "CodTramoBT"
    assert suggestion.mapping.lines.fields.get("name") != "CodTramoBTPadre"


def test_suggest_mapping_does_not_use_commissioning_date_as_bus_name() -> None:
    schema = DatasetSchema(
        tables=(
            TableSchema(
                "btPuntoConexionSuministro",
                100,
                (
                    _column("CodAcometida", unique=100),
                    _column("FecPuestaServicio", "datetime64[ns]", unique=3),
                    _column("UTMEste", "float64", 100),
                    _column("UTMNorte", "float64", 100),
                ),
                False,
                None,
                None,
                None,
            ),
        )
    )
    suggestion = suggest_mapping(schema, seed=11, population_size=16, generations=8)

    assert suggestion.mapping.buses is not None
    assert suggestion.mapping.buses.fields["id"] == "CodAcometida"
    assert suggestion.mapping.buses.fields.get("name") != "FecPuestaServicio"


def test_suggest_mapping_rejects_district_as_to_bus_and_prefers_bt_tramo() -> None:
    schema = DatasetSchema(
        tables=(
            TableSchema(
                "BD_SED",
                100,
                (
                    _column("ID", "int32", 100),
                    _column("CÓDIGO", unique=100),
                    _column("TENSIÓN NOMINAL MT (KV)", unique=4),
                    _column("CANT FASE", "int8", 3),
                    ColumnSchema("Descripción", "float32", True, 0, 0),
                ),
                False,
                None,
                None,
                None,
            ),
            TableSchema(
                "BD_Tramo AT",
                50,
                (
                    _column("ID", "int32", 50),
                    _column("CÓDIGO TRAMO PADRE", "float32", 40),
                    _column("DISTRITO", unique=10),
                    _column("LONGITUD REAL (M)", "float64", 50),
                    _column("NIVEL DE TENSIÓN (KV)", unique=2),
                ),
                False,
                None,
                None,
                None,
            ),
            TableSchema(
                "BD_Tramo BT",
                200,
                (
                    _column("ID", "int32", 200),
                    _column("CÓDIGO TRAMO PADRE", "object", 180),
                    _column("SALIDA SED", unique=40),
                    _column("LONGITUD REAL (m)", "float32", 200),
                    _column("NIVEL DE TENSION (KV)", unique=3),
                ),
                False,
                None,
                None,
                None,
            ),
            TableSchema(
                "BD_Salida MT",
                20,
                (
                    _column("ID", "int32", 20),
                    _column("SET", unique=5),
                    _column("NIVEL DE TENSIÓN", unique=2),
                    ColumnSchema("Descripción", "float32", True, 0, 0),
                ),
                False,
                None,
                None,
                None,
            ),
            TableSchema(
                "BD_Salida AT",
                10,
                (
                    _column("ID", "int32", 10),
                    _column("SET", unique=4),
                    ColumnSchema("Descripción", "float32", True, 0, 0),
                ),
                False,
                None,
                None,
                None,
            ),
        )
    )
    suggestion = suggest_mapping(schema, seed=5, population_size=20, generations=10)
    assert suggestion.mapping.lines is not None
    assert suggestion.mapping.lines.source == "BD_Tramo BT"
    assert suggestion.mapping.lines.fields.get("to_bus") != "DISTRITO"
    assert suggestion.mapping.lines.fields.get("to_bus") in {
        "ID",
        suggestion.mapping.lines.fields.get("id"),
    }
    if suggestion.mapping.buses is not None:
        assert suggestion.mapping.buses.fields.get("x") != "CANT FASE"
        assert suggestion.mapping.buses.fields.get("name") != "Descripción"
    if suggestion.mapping.sources is not None:
        assert suggestion.mapping.sources.source in {"BD_Salida MT", "BD_Salida AT"}
        assert suggestion.mapping.sources.fields.get("nominal_voltage_kv") != "Descripción"


def test_infer_active_power_unit_prefers_kw_for_pac() -> None:
    from gis2dgs.assist.service import _infer_active_power_unit

    assert _infer_active_power_unit("PAC") == "kW"
    assert _infer_active_power_unit("potencia_kw") == "kW"
    assert _infer_active_power_unit("p_mw") == "MW"
    assert _infer_active_power_unit("MÁXIMA DEMANDA (kW)") == "kW"


def test_sanitize_load_power_rejects_ubicacion_as_reactive() -> None:
    from gis2dgs.assist.service import _sanitize_load_power_fields

    table = TableSchema(
        "BD_Acometidas",
        100,
        (
            ColumnSchema("ID", "int32", False, 100, 100),
            ColumnSchema("SED", "str", False, 100, 20),
            ColumnSchema("PAC", "float32", True, 80, 30),
            ColumnSchema("UBICACION GEOGRAFICA", "int32", False, 100, 10),
        ),
        False,
        None,
        None,
        None,
    )
    fields = {
        "id": "ID",
        "bus_id": "SED",
        "active_power_mw": "PAC",
        "reactive_power_mvar": "UBICACION GEOGRAFICA",
    }
    _sanitize_load_power_fields(table, fields)
    assert fields["active_power_mw"] == "PAC"
    assert "reactive_power_mvar" not in fields


def test_suggest_mapping_acometidas_pac_defaults_and_kw_unit() -> None:
    dataset = InputDataset()
    dataset.add_table(
        "buses",
        pd.DataFrame({"id": ["B1"], "voltage_kv": [10.0]}),
    )
    dataset.add_table(
        "lines",
        pd.DataFrame(
            {
                "id": ["L1"],
                "from_bus": ["B1"],
                "to_bus": ["B1"],
                "length_km": [0.1],
                "voltage_kv": [10.0],
            }
        ),
    )
    dataset.add_table(
        "BD_Acometidas",
        pd.DataFrame(
            {
                "ID": [1, 2],
                "SED": ["B1", "B1"],
                "PAC": [33.0, None],
                "UBICACION GEOGRAFICA": [10, 20],
                "METER": ["M1", "M2"],
            }
        ),
    )
    suggestion = suggest_mapping(
        discover_schema(dataset), seed=9, population_size=16, generations=8
    )
    assert suggestion.mapping.loads is not None
    assert suggestion.mapping.loads.source == "BD_Acometidas"
    assert suggestion.mapping.loads.fields.get("active_power_mw") == "PAC"
    assert suggestion.mapping.loads.units.get("active_power_mw") == "kW"
    assert suggestion.mapping.loads.defaults.get("active_power_mw") == 0.0
    assert suggestion.mapping.loads.fields.get("reactive_power_mvar") != "UBICACION GEOGRAFICA"


def test_sanitize_bus_id_prefers_codigo_over_surrogate_id() -> None:
    from gis2dgs.assist.service import _sanitize_bus_id_field

    table = TableSchema(
        "BD_SED",
        3,
        (
            ColumnSchema("ID", "int32", False, 3, 3),
            ColumnSchema("CÓDIGO", "str", False, 3, 3),
            ColumnSchema("CÓDIGO NORMA", "str", False, 3, 2),
            ColumnSchema("TENSIÓN NOMINAL MT (KV)", "str", False, 3, 2),
        ),
        False,
        None,
        None,
        None,
    )
    fields = {"id": "ID", "nominal_voltage_kv": "TENSIÓN NOMINAL MT (KV)"}
    _sanitize_bus_id_field(table, fields)
    assert fields["id"] == "CÓDIGO"


def test_prefer_candidate_with_buses_over_busless_topsis() -> None:
    """When the front has buses, TOPSIS must not leave convert blocked."""

    dataset = InputDataset()
    dataset.add_table(
        "BD_SED",
        pd.DataFrame(
            {
                "ID": [1, 2],
                "CÓDIGO": ["SE1", "SE2"],
                "TENSIÓN NOMINAL MT (KV)": ["10,0", "22,9"],
                "NOMBRE": ["A", "B"],
            }
        ),
    )
    dataset.add_table(
        "BD_Tramo AT",
        pd.DataFrame(
            {
                "ID": [10, 11],
                "CÓDIGO TRAMO PADRE": [11, 10],
                "LONGITUD REAL (M)": [100.0, 200.0],
                "NIVEL DE TENSIÓN (KV)": [10.0, 10.0],
                "TIPO DE TENDIDO": ["AEREO", "AEREO"],
                "ESTADO INSTALACIÓN": ["OPERATIVO", "OPERATIVO"],
            }
        ),
    )
    dataset.add_table(
        "BD_Acometidas",
        pd.DataFrame(
            {
                "ID": [1],
                "SED": ["SE1"],
                "PAC": [5.0],
                "METER": ["M1"],
                "ESTADO INSTALACIÓN": ["OPERATIVO"],
            }
        ),
    )
    dataset.add_table(
        "BD_AMT",
        pd.DataFrame(
            {
                "ID": [1],
                "SET": ["S1"],
                "TENSIÓN NOMINAL": [10.0],
                "LOCALIDAD": ["L1"],
                "Existe desde": ["2020"],
            }
        ),
    )
    dataset.add_table(
        "BD_SET",
        pd.DataFrame({"ID": [1], "NOMBRE": ["SET1"]}),
    )
    suggestion = suggest_mapping(
        discover_schema(dataset),
        seed=6,
        population_size=24,
        generations=10,
    )
    assert suggestion.mapping.buses is not None
    assert suggestion.mapping.buses.source == "BD_SED"
    assert suggestion.mapping.buses.fields["id"] == "CÓDIGO"
    assert any(
        (item.get("summary") or {}).get("buses") == "BD_SED" for item in suggestion.pareto
    )


def test_voltage_column_type_ok_for_string_kv() -> None:
    from gis2dgs.assist.service import _voltage_column_type_ok

    assert _voltage_column_type_ok(
        ColumnSchema("TENSIÓN NOMINAL MT (KV)", "str", False, 10, 4)
    )
    assert _voltage_column_type_ok(ColumnSchema("voltage_kv", "float64", False, 10, 2))
    assert not _voltage_column_type_ok(ColumnSchema("nombre", "str", False, 10, 8))
