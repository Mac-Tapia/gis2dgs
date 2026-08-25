from datetime import date, datetime
from math import isnan
import re
from typing import Any

import pandas as pd


def is_missing(value: Any) -> bool:
    """Return True for None/NaN/pandas missing scalars without accepting arrays."""

    if value is None:
        return True
    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(result) if isinstance(result, bool) else False


def normalize_identifier(value: Any) -> str:
    if is_missing(value):
        raise ValueError("Identifier cannot be empty.")
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid identifiers.")
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        text = str(value).strip()
        if not text:
            raise ValueError("Identifier cannot be empty.")
        return text
    if isinstance(value, int):
        return str(value)
    text = str(value).strip()
    if not text:
        raise ValueError("Identifier cannot be empty.")
    if text.endswith(".0") and text.replace(".", "", 1).lstrip("-").isdigit():
        try:
            number = float(text)
        except ValueError:
            return text
        if number.is_integer():
            return str(int(number))
    return text


def normalize_optional_identifier(value: Any) -> str | None:
    if is_missing(value):
        return None
    try:
        return normalize_identifier(value)
    except ValueError:
        return None


def normalize_name(value: Any, *, fallback: str) -> str:
    if is_missing(value):
        return fallback
    text = str(value).strip()
    return text or fallback


def normalize_number(value: Any) -> float:
    """Parse numeric GIS values, including simple decimal-comma strings."""

    if is_missing(value):
        raise ValueError("Numeric value cannot be empty.")

    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid numeric values here.")

    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().replace(" ", "")
        if not text:
            raise ValueError("Numeric value cannot be empty.")
        if "," in text and "." not in text:
            text = text.replace(",", ".")
        try:
            number = float(text)
        except ValueError as exc:
            raise ValueError(f"Invalid numeric value: {value!r}") from exc

    if isnan(number):
        raise ValueError("Numeric value cannot be NaN.")
    return number


def normalize_switch_state(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if is_missing(value):
        raise ValueError("Switch state cannot be empty.")

    text = str(value).strip().upper()
    closed_values = {"1", "C", "CLOSED", "CERRADO", "ON", "TRUE", "SI", "SÍ"}
    open_values = {"0", "O", "OPEN", "ABIERTO", "OFF", "FALSE", "NO"}
    if text in closed_values:
        return True
    if text in open_values:
        return False
    raise ValueError(f"Unsupported switch state: {value!r}")


def normalize_service_state(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if is_missing(value):
        raise ValueError("Service state cannot be empty.")
    # Commissioning / "exists since" columns: a concrete date means installed.
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return True

    text = str(value).strip().upper()
    active_values = {
        "1",
        "TRUE",
        "ON",
        "SI",
        "SÍ",
        "S",
        "E",
        "ACTIVE",
        "ACTIVO",
        "IN_SERVICE",
        "EN SERVICIO",
        "VNR",
        # Feeder/switch inventory: closed breaker ⇒ energized path
        "CERRADO",
        "C",
        "OPERANDO",
        "OPERATIVO",
        "EN OPERACION",
        "EN OPERACIÓN",
        "INSTALADO",
        "ENERGIZADO",
    }
    inactive_values = {
        "0",
        "FALSE",
        "OFF",
        "NO",
        "N",
        "F",
        "R",
        "INACTIVE",
        "INACTIVO",
        "OUT_OF_SERVICE",
        "FUERA DE SERVICIO",
        "RETIRADO",
        "ABIERTO",
        "O",
        "DESENERGIZADO",
        "DESINSTALADO",
        "PROYECTADO",
        "NO INSTALADO",
        "BAJA",
    }
    if text in active_values:
        return True
    if text in inactive_values:
        return False
    raise ValueError(f"Unsupported service state: {value!r}")


def convert_voltage_to_kv(
    value: Any,
    unit: str = "kV",
    *,
    code_lookup: dict[str, float] | None = None,
) -> float:
    if code_lookup is not None:
        try:
            number = normalize_number(value)
        except ValueError:
            code = normalize_identifier(value)
            if code not in code_lookup:
                raise ValueError(f"Unknown voltage code: {value!r}") from None
            number = code_lookup[code]
        factors = {"V": 1e-3, "kV": 1.0}
        return _convert(number, unit, factors, "voltage")

    number, inferred_unit = _parse_voltage_token(value)
    factors = {"V": 1e-3, "kV": 1.0}
    return _convert(number, inferred_unit or unit, factors, "voltage")


_VOLTAGE_TOKEN = re.compile(
    r"^\s*([+-]?\d+(?:[.,]\d+)?)\s*(kV|KV|kv|V|v)?\s*$"
)


def _parse_voltage_token(value: Any) -> tuple[float, str | None]:
    """Parse ``60 KV``, ``22,9kV`` or plain numbers into (magnitude, unit|None)."""

    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid numeric values here.")
    if isinstance(value, (int, float)):
        return float(value), None
    text = str(value).strip()
    match = _VOLTAGE_TOKEN.match(text)
    if match is None:
        return normalize_number(value), None
    number = normalize_number(match.group(1))
    suffix = match.group(2)
    if suffix is None:
        return number, None
    return number, "kV" if suffix.upper() == "KV" else "V"


def convert_length_to_km(value: Any, unit: str = "km") -> float:
    number = normalize_number(value)
    factors = {"m": 1e-3, "km": 1.0}
    return _convert(number, unit, factors, "length")


def convert_active_power_to_mw(value: Any, unit: str = "MW") -> float:
    number = normalize_number(value)
    factors = {"W": 1e-6, "kW": 1e-3, "MW": 1.0}
    return _convert(number, unit, factors, "active power")


def convert_reactive_power_to_mvar(value: Any, unit: str = "Mvar") -> float:
    number = normalize_number(value)
    factors = {"var": 1e-6, "kvar": 1e-3, "Mvar": 1.0}
    return _convert(number, unit, factors, "reactive power")


def convert_apparent_power_to_mva(value: Any, unit: str = "MVA") -> float:
    number = normalize_number(value)
    factors = {"VA": 1e-6, "kVA": 1e-3, "MVA": 1.0}
    return _convert(number, unit, factors, "apparent power")


def volts_to_kv(volts: float) -> float:
    return convert_voltage_to_kv(volts, "V")


def metres_to_km(metres: float) -> float:
    return convert_length_to_km(metres, "m")


def _convert(number: float, unit: str, factors: dict[str, float], quantity: str) -> float:
    normalized = {key.casefold(): key for key in factors}
    canonical = normalized.get(str(unit).strip().casefold())
    if canonical is None:
        raise ValueError(f"Unsupported {quantity} unit: {unit}")
    return number * factors[canonical]
