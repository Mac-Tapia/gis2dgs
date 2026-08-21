from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from .exceptions import DuplicatePowerFactoryObjectError


@dataclass(frozen=True, slots=True)
class PowerFactoryReference:
    """Semantic object reference resolved by stable foreign key."""

    target_key: str

    def __post_init__(self) -> None:
        if not self.target_key.strip():
            raise ValueError("PowerFactory reference target cannot be empty.")


@dataclass(frozen=True, slots=True)
class PowerFactoryObject:
    """Version-neutral PowerFactory object before DGS field serialization.

    `attributes` and `references` deliberately use semantic names. Phase 8 will
    translate those semantic names into the DGS columns defined by the
    configured schema/reference export.
    """

    class_name: str
    foreign_key: str
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    references: dict[str, PowerFactoryReference] = field(default_factory=dict)
    parent: PowerFactoryReference | None = None
    source_kind: str | None = None
    source_id: str | None = None

    def __post_init__(self) -> None:
        if not self.class_name.strip():
            raise ValueError("PowerFactory class name cannot be empty.")
        if not self.foreign_key.strip():
            raise ValueError("PowerFactory foreign key cannot be empty.")
        if not self.name.strip():
            raise ValueError("PowerFactory object name cannot be empty.")


@dataclass(slots=True)
class PowerFactoryModel:
    """Canonical node-breaker representation prepared for DGS serialization."""

    objects: dict[str, PowerFactoryObject] = field(default_factory=dict)

    def add(self, obj: PowerFactoryObject) -> None:
        if obj.foreign_key in self.objects:
            raise DuplicatePowerFactoryObjectError(
                f"Duplicate PowerFactory foreign key: {obj.foreign_key}"
            )
        self.objects[obj.foreign_key] = obj

    def get(self, foreign_key: str) -> PowerFactoryObject:
        try:
            return self.objects[foreign_key]
        except KeyError as exc:
            raise KeyError(f"Unknown PowerFactory foreign key: {foreign_key}") from exc

    def find_by_class(self, class_name: str) -> tuple[PowerFactoryObject, ...]:
        return tuple(obj for obj in self.objects.values() if obj.class_name == class_name)

    def extend(self, objects: Iterable[PowerFactoryObject]) -> None:
        for obj in objects:
            self.add(obj)

    def class_counts(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for obj in self.objects.values():
            counts[obj.class_name] += 1
        return dict(sorted(counts.items()))

    def summary(self) -> dict[str, object]:
        return {
            "objects": len(self.objects),
            "classes": self.class_counts(),
        }
