from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from enum import StrEnum

from .model import PowerFactoryModel


class MappingSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True, slots=True)
class PowerFactoryMappingIssue:
    code: str
    severity: MappingSeverity
    message: str
    object_key: str | None = None


@dataclass(frozen=True, slots=True)
class PowerFactoryMappingReport:
    issues: tuple[PowerFactoryMappingIssue, ...]

    @property
    def errors(self) -> tuple[PowerFactoryMappingIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == MappingSeverity.ERROR)

    @property
    def warnings(self) -> tuple[PowerFactoryMappingIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == MappingSeverity.WARNING)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def ensure_unique_display_names(model: PowerFactoryModel) -> None:
    """Replace colliding loc_name values with source IDs so PowerFactory will not rename."""

    scopes: dict[tuple[str, str | None], list[str]] = defaultdict(list)
    for key, obj in model.objects.items():
        parent_key = obj.parent.target_key if obj.parent is not None else None
        scopes[(obj.class_name, parent_key)].append(key)

    for keys in scopes.values():
        name_counts: dict[str, int] = {}
        for key in keys:
            name = model.objects[key].name
            name_counts[name] = name_counts.get(name, 0) + 1
        used: set[str] = set()
        for key in keys:
            obj = model.objects[key]
            name = obj.name
            if name_counts[name] > 1 or name in used:
                fallback = (obj.source_id or "").strip()
                if not fallback:
                    fallback = obj.foreign_key.rsplit(":", 1)[-1]
                name = fallback
                suffix = 2
                while name in used:
                    name = f"{fallback}_{suffix}"
                    suffix += 1
                if name != obj.name:
                    model.objects[key] = replace(obj, name=name)
            used.add(name)


def validate_powerfactory_model(model: PowerFactoryModel) -> PowerFactoryMappingReport:
    """Validate parent/reference integrity of the mapped PowerFactory model."""

    issues: list[PowerFactoryMappingIssue] = []
    known = set(model.objects)
    names_by_scope: dict[tuple[str, str | None], dict[str, str]] = {}

    for obj in model.objects.values():
        parent_key = obj.parent.target_key if obj.parent is not None else None
        scope = (obj.class_name, parent_key)
        scoped_names = names_by_scope.setdefault(scope, {})
        if obj.name in scoped_names:
            issues.append(
                PowerFactoryMappingIssue(
                    code="PFM003",
                    severity=MappingSeverity.ERROR,
                    object_key=obj.foreign_key,
                    message=(
                        f"Object {obj.foreign_key} ({obj.class_name}) duplicates display "
                        f"name {obj.name!r} within the same parent folder; PowerFactory "
                        "would rename it on import."
                    ),
                )
            )
        else:
            scoped_names[obj.name] = obj.foreign_key

    for obj in model.objects.values():
        if obj.parent is not None and obj.parent.target_key not in known:
            issues.append(
                PowerFactoryMappingIssue(
                    code="PFM001",
                    severity=MappingSeverity.ERROR,
                    object_key=obj.foreign_key,
                    message=(
                        f"Object {obj.foreign_key} has missing parent "
                        f"{obj.parent.target_key}."
                    ),
                )
            )
        for role, reference in obj.references.items():
            if reference.target_key not in known:
                issues.append(
                    PowerFactoryMappingIssue(
                        code="PFM002",
                        severity=MappingSeverity.ERROR,
                        object_key=obj.foreign_key,
                        message=(
                            f"Object {obj.foreign_key} reference {role!r} targets missing "
                            f"object {reference.target_key}."
                        ),
                    )
                )

    return PowerFactoryMappingReport(tuple(issues))
