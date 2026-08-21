from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    required: bool
    aliases: tuple[str, ...]
    numeric: bool = False


@dataclass(frozen=True, slots=True)
class EntitySpec:
    name: str
    table_aliases: tuple[str, ...]
    fields: tuple[FieldSpec, ...]


ENTITIES: tuple[EntitySpec, ...] = (
    EntitySpec(
        "buses",
        (
            "bus",
            "buses",
            "barra",
            "barras",
            "nodo",
            "nodos",
            "node",
            "nodes",
            "busbar",
            "nodoenlace",
            "enlace",
            "punto",
            "puntoconexion",
        ),
        (
            FieldSpec(
                "id",
                True,
                ("id", "codigo", "code", "fid", "objectid", "cod_nodo", "codnodo"),
                False,
            ),
            FieldSpec(
                "nominal_voltage_kv",
                True,
                (
                    "nominal_voltage_kv",
                    "voltage_kv",
                    "tension",
                    "voltaje",
                    "kv",
                    "uknom",
                    "voltage",
                    "codtennomi",
                    "tennomi",
                    "tennom",
                ),
                True,
            ),
            FieldSpec(
                "x",
                False,
                ("x", "este", "east", "lon", "longitude", "utmeste", "utme"),
                True,
            ),
            FieldSpec(
                "y",
                False,
                ("y", "norte", "north", "lat", "latitude", "utmnorte", "utmn"),
                True,
            ),
            FieldSpec("name", False, ("name", "nombre", "loc_name", "descripcion", "etiqueta"), False),
        ),
    ),
    EntitySpec(
        "lines",
        ("line", "lines", "linea", "lineas", "tramo", "tramos", "conductor", "span"),
        (
            FieldSpec(
                "id",
                True,
                ("id", "codigo", "code", "fid", "cod_tramo", "codtramo", "codtramobt", "codtramomt"),
                False,
            ),
            FieldSpec("name", False, ("name", "nombre", "loc_name"), False),
            FieldSpec(
                "from_bus",
                True,
                (
                    "from_bus",
                    "nodo_i",
                    "bus1",
                    "from",
                    "origen",
                    "node_from",
                    "codnodo",
                    "nodo_origen",
                ),
                False,
            ),
            FieldSpec(
                "to_bus",
                True,
                ("to_bus", "nodo_f", "bus2", "to", "destino", "node_to", "codnodo"),
                False,
            ),
            FieldSpec(
                "length_km",
                True,
                ("length_km", "length", "longitud", "long_km", "dline"),
                True,
            ),
            FieldSpec(
                "nominal_voltage_kv",
                True,
                (
                    "nominal_voltage_kv",
                    "voltage_kv",
                    "tension",
                    "voltaje",
                    "kv",
                    "voltage",
                    "codtennomi",
                    "tennomi",
                ),
                True,
            ),
            FieldSpec(
                "type_id",
                False,
                (
                    "type_id",
                    "tipo",
                    "conductor",
                    "cod_cond",
                    "codnorma",
                    "norma",
                    "codnormafase",
                ),
                False,
            ),
            FieldSpec("in_service", False, ("in_service", "estado", "outserv"), False),
        ),
    ),
    EntitySpec(
        "loads",
        ("load", "loads", "carga", "cargas", "consumo"),
        (
            FieldSpec("id", True, ("id", "codigo", "code", "fid"), False),
            FieldSpec("name", False, ("name", "nombre"), False),
            FieldSpec("bus_id", True, ("bus_id", "nodo", "barra", "bus"), False),
            FieldSpec(
                "active_power_mw",
                True,
                ("active_power_mw", "p_mw", "p", "potencia", "dmax", "kw"),
                True,
            ),
            FieldSpec(
                "reactive_power_mvar",
                False,
                ("reactive_power_mvar", "q_mvar", "q", "kvar"),
                True,
            ),
            FieldSpec("in_service", False, ("in_service", "estado"), False),
        ),
    ),
    EntitySpec(
        "sources",
        ("source", "sources", "fuente", "fuentes", "grid", "alimentad", "alimentador", "feeder", "salida"),
        (
            FieldSpec("id", True, ("id", "codigo", "code", "fid"), False),
            FieldSpec("name", False, ("name", "nombre"), False),
            FieldSpec("bus_id", True, ("bus_id", "nodo", "barra", "bus", "conexionn"), False),
            FieldSpec(
                "nominal_voltage_kv",
                True,
                ("nominal_voltage_kv", "voltage_kv", "tension", "voltaje", "kv"),
                True,
            ),
            FieldSpec("in_service", False, ("in_service", "estado"), False),
        ),
    ),
    EntitySpec(
        "transformers",
        ("transformer", "transformers", "trafo", "trafos", "transformador"),
        (
            FieldSpec("id", True, ("id", "codigo", "fid"), False),
            FieldSpec("name", False, ("name", "nombre"), False),
            FieldSpec("hv_bus", True, ("hv_bus", "nodo_at", "bus_hv", "alta"), False),
            FieldSpec("lv_bus", True, ("lv_bus", "nodo_bt", "bus_lv", "baja"), False),
            FieldSpec("hv_voltage_kv", True, ("hv_voltage_kv", "tension_at", "uhv"), True),
            FieldSpec("lv_voltage_kv", True, ("lv_voltage_kv", "tension_bt", "ulv"), True),
            FieldSpec(
                "rated_power_mva",
                True,
                ("rated_power_mva", "s_mva", "potencia", "snom"),
                True,
            ),
            FieldSpec("type_id", False, ("type_id", "tipo"), False),
        ),
    ),
    EntitySpec(
        "switches",
        ("switch", "switches", "seccionador", "interruptor", "breaker"),
        (
            FieldSpec("id", True, ("id", "codigo", "fid"), False),
            FieldSpec("name", False, ("name", "nombre"), False),
            FieldSpec("from_bus", True, ("from_bus", "nodo_i", "bus1"), False),
            FieldSpec("to_bus", True, ("to_bus", "nodo_f", "bus2"), False),
            FieldSpec("closed", False, ("closed", "cerrado", "on_off", "estado"), False),
        ),
    ),
    EntitySpec(
        "generators",
        ("generator", "generators", "generador", "generacion", "der", "pv"),
        (
            FieldSpec("id", True, ("id", "codigo", "fid"), False),
            FieldSpec("name", False, ("name", "nombre"), False),
            FieldSpec("bus_id", True, ("bus_id", "nodo", "barra"), False),
            FieldSpec("active_power_mw", True, ("active_power_mw", "p_mw", "p", "potencia"), True),
            FieldSpec("reactive_power_mvar", False, ("reactive_power_mvar", "q_mvar", "q"), True),
            FieldSpec("technology", False, ("technology", "tecnologia", "tipo"), False),
        ),
    ),
    EntitySpec(
        "substations",
        ("substation", "substations", "subestacion", "set", "estacion"),
        (
            FieldSpec("id", True, ("id", "codigo", "codset", "fid"), False),
            FieldSpec("name", False, ("name", "nombre"), False),
            FieldSpec("x", False, ("x", "este", "east"), True),
            FieldSpec("y", False, ("y", "norte", "north"), True),
        ),
    ),
)
