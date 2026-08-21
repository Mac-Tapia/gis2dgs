from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .exceptions import DuplicateElectricalTypeError, UnknownElectricalTypeError
from .models import LineType, TransformerType


@dataclass(slots=True)
class ElectricalLibrary:
    """Canonical electrical equipment-type library.

    The library is intentionally independent from GIS and DGS schemas. Network
    elements reference its types by stable string identifiers.
    """

    line_types: dict[str, LineType] = field(default_factory=dict)
    transformer_types: dict[str, TransformerType] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for type_id, line_type in self.line_types.items():
            if type_id != line_type.id:
                raise ValueError(
                    f"Line type dictionary key {type_id!r} does not match object ID "
                    f"{line_type.id!r}."
                )
        for type_id, transformer_type in self.transformer_types.items():
            if type_id != transformer_type.id:
                raise ValueError(
                    f"Transformer type dictionary key {type_id!r} does not match object ID "
                    f"{transformer_type.id!r}."
                )

    @classmethod
    def from_types(
        cls,
        *,
        line_types: Iterable[LineType] = (),
        transformer_types: Iterable[TransformerType] = (),
    ) -> "ElectricalLibrary":
        library = cls()
        for line_type in line_types:
            library.add_line_type(line_type)
        for transformer_type in transformer_types:
            library.add_transformer_type(transformer_type)
        return library

    def add_line_type(self, line_type: LineType) -> None:
        if line_type.id in self.line_types:
            raise DuplicateElectricalTypeError(
                f"Duplicate line type ID: {line_type.id}"
            )
        self.line_types[line_type.id] = line_type

    def add_transformer_type(self, transformer_type: TransformerType) -> None:
        if transformer_type.id in self.transformer_types:
            raise DuplicateElectricalTypeError(
                f"Duplicate transformer type ID: {transformer_type.id}"
            )
        self.transformer_types[transformer_type.id] = transformer_type

    def find_line_type(self, type_id: str) -> LineType | None:
        return self.line_types.get(type_id)

    def find_transformer_type(self, type_id: str) -> TransformerType | None:
        return self.transformer_types.get(type_id)

    def get_line_type(self, type_id: str) -> LineType:
        line_type = self.find_line_type(type_id)
        if line_type is None:
            raise UnknownElectricalTypeError(f"Unknown line type ID: {type_id}")
        return line_type

    def get_transformer_type(self, type_id: str) -> TransformerType:
        transformer_type = self.find_transformer_type(type_id)
        if transformer_type is None:
            raise UnknownElectricalTypeError(f"Unknown transformer type ID: {type_id}")
        return transformer_type

    @property
    def is_empty(self) -> bool:
        return not self.line_types and not self.transformer_types

    def summary(self) -> dict[str, int]:
        return {
            "line_types": len(self.line_types),
            "transformer_types": len(self.transformer_types),
            "total_types": len(self.line_types) + len(self.transformer_types),
        }
