from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class DgsColumnType(StrEnum):
    TEXT = "a"
    INTEGER = "i"
    REAL = "r"
    POINTER = "p"
    UNKNOWN = "unknown"


_HEADER_RE = re.compile(r"^(?P<name>[^()]+)\((?P<type>[a-zA-Z])(?::(?P<size>\d+))?\)$")


@dataclass(frozen=True, slots=True)
class DgsColumnDefinition:
    raw: str
    name: str
    type: DgsColumnType
    size: int | None = None

    @classmethod
    def parse(cls, header: str) -> "DgsColumnDefinition":
        raw = header.strip()
        match = _HEADER_RE.match(raw)
        if match is None:
            return cls(raw=raw, name=raw, type=DgsColumnType.UNKNOWN)
        code = match.group("type").lower()
        try:
            column_type = DgsColumnType(code)
        except ValueError:
            column_type = DgsColumnType.UNKNOWN
        size_text = match.group("size")
        return cls(
            raw=raw,
            name=match.group("name").strip(),
            type=column_type,
            size=int(size_text) if size_text is not None else None,
        )
