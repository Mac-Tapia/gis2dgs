from __future__ import annotations

from typing import Protocol

from .dataset import InputDataset


class InputReader(Protocol):
    def read(self) -> InputDataset:
        """Read one source without creating electrical-domain objects."""
        ...
