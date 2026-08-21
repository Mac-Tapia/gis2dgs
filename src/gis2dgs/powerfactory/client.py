from pathlib import Path
from typing import Protocol


class PowerFactoryClient(Protocol):
    """Port implemented later by the target PowerFactory installation adapter."""

    def import_dgs(self, dgs_path: Path) -> None: ...

    def run_load_flow(self) -> bool: ...
