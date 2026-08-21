from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_SAFE = re.compile(r"[^A-Za-z0-9_.:-]+")


@dataclass(frozen=True, slots=True)
class ForeignKeyFactory:
    """Create deterministic, PowerFactory-safe foreign keys.

    The default maximum length is 40 characters. Long keys are shortened with a
    stable digest so GIS identifiers remain deterministic without silent
    collisions. Foreign keys remain case-sensitive.
    """

    prefix: str = "GIS2DGS"
    max_length: int = 40

    def __post_init__(self) -> None:
        if not self.prefix.strip():
            raise ValueError("Foreign-key prefix cannot be empty.")
        if self.max_length < 12:
            raise ValueError("Foreign-key max_length must be at least 12 characters.")

    def make(self, kind: str, raw_id: object) -> str:
        raw = str(raw_id).strip()
        kind_clean = self._clean(kind)
        if not raw:
            raise ValueError("Foreign-key source ID cannot be empty.")
        clean = self._clean(raw)
        if clean != raw:
            digest = self._digest(raw)
            clean = f"{clean}~{digest}"

        key = f"{self._clean(self.prefix)}:{kind_clean}:{clean}"
        if len(key) <= self.max_length:
            return key

        digest = self._digest(key)
        suffix = f"~{digest}"
        return f"{key[: self.max_length - len(suffix)]}{suffix}"

    def cubicle(self, element_key: str, side: str) -> str:
        return self.make("cub", f"{element_key}:{side}")

    @staticmethod
    def _digest(value: str) -> str:
        return hashlib.blake2s(value.encode("utf-8"), digest_size=4).hexdigest()

    @staticmethod
    def _clean(value: str) -> str:
        cleaned = _SAFE.sub("_", value.strip())
        cleaned = cleaned.strip("_")
        if not cleaned:
            raise ValueError("Foreign-key token cannot be empty after normalization.")
        return cleaned
