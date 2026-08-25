"""Select tabular inventory files that contribute to a DGS network model.

Non-electrical layers (roads, guy wires, lighting, concession polygons, etc.)
are left on disk and never inspected or converted.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

_DATE_TOKEN = re.compile(
    r"(?:^|[_\s.-])("
    r"20\d{2}[-_.]?\d{2}[-_.]?\d{2}"
    r"|"
    r"\d{2}[-_.]\d{2}[-_.]20\d{2}"
    r"|"
    r"20\d{6}"
    r")(?:$|[_\s.-])"
)

# Filename tokens that mark network / electrical inventory layers.
_INCLUDE_MARKERS: tuple[tuple[str, ...], ...] = (
    ("transformador",),
    ("transformer",),
    ("transformers",),
    ("tramo", "bt"),
    ("tramo", "mt"),
    ("tramo", "at"),
    ("tramo",),  # generic span; excluded if also road markers
    ("sed",),
    ("set",),
    ("salida",),
    ("amt",),
    ("alimentador",),
    ("suministro",),
    ("suministros",),
    ("acometida",),
    ("acometidas",),
    ("proteccion",),
    ("centro", "generacion"),
    ("generacion",),
    ("condensador",),
    ("condensadores",),
    ("banco", "condensador"),
    ("banco", "condensadores"),
    # Canonical / English tabular packages (examples/minimal, generic CSV).
    ("buses",),
    ("bus",),
    ("lines",),
    ("line",),
    ("loads",),
    ("load",),
    ("sources",),
    ("source",),
    ("switches",),
    ("switch",),
    ("generators",),
    ("generator",),
    ("substations",),
    ("substation",),
    ("nodos",),
    ("nodo",),
    ("nodes",),
    ("node",),
)

# Filename tokens that never feed the electrical NetworkModel → DGS path.
_SKIP_MARKERS: tuple[tuple[str, ...], ...] = (
    ("tramo", "via"),
    ("tramo", "vía"),
    ("zona", "concesion"),
    ("zona", "concesión"),
    ("retenida",),
    ("pararrayos",),
    ("estructuras",),
    ("alumbrado",),
    ("uap",),
    ("pastoral",),
    # Grounding inventory (PAT) — not a DGS topology element here.
    ("pat",),
)


@dataclass(frozen=True, slots=True)
class DgsRelevanceDecision:
    path: Path
    include: bool
    reason: str
    group_key: str


def normalize_filename_token(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_only = "".join(char for char in folded if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", ascii_only).strip()


def _tokens(path: Path) -> frozenset[str]:
    return frozenset(normalize_filename_token(path.stem).split())


def _matches_markers(tokens: frozenset[str], markers: tuple[tuple[str, ...], ...]) -> bool:
    for marker in markers:
        if all(part in tokens for part in marker):
            return True
    return False


def is_dgs_relevant_tabular_file(path: Path) -> bool:
    """Return True when a tabular file name suggests electrical network content."""

    tokens = _tokens(path)
    if not tokens:
        return False
    if _matches_markers(tokens, _SKIP_MARKERS):
        return False
    # Lone "pat" as whole stem/token after BD_ strip
    if tokens <= {"bd", "pat"} or tokens == {"pat"}:
        return False
    return _matches_markers(tokens, _INCLUDE_MARKERS)


def group_key_for_path(path: Path) -> str:
    """Stable key for dated export duplicates (BD_SED vs BD_SED_15.01.2025)."""

    stem = path.stem
    cleaned = _DATE_TOKEN.sub(" ", stem)
    return normalize_filename_token(cleaned)


def _date_rank(path: Path) -> tuple[int, str]:
    match = _DATE_TOKEN.search(path.stem)
    if match is None:
        # Prefer undated "current" inventory over older dated copies when both exist.
        return (1, path.name.lower())
    return (0, match.group(1))


def classify_dgs_relevance(path: Path) -> DgsRelevanceDecision:
    resolved = path.expanduser().resolve()
    key = group_key_for_path(resolved)
    if is_dgs_relevant_tabular_file(resolved):
        return DgsRelevanceDecision(
            path=resolved,
            include=True,
            reason="capa eléctrica / topológica para NetworkModel→DGS",
            group_key=key,
        )
    return DgsRelevanceDecision(
        path=resolved,
        include=False,
        reason="capa auxiliar (vía, zona, retenida, PAT, estructuras, UAP, etc.)",
        group_key=key,
    )


def filter_dgs_relevant_paths(
    paths: tuple[Path, ...] | list[Path],
) -> tuple[tuple[Path, ...], tuple[DgsRelevanceDecision, ...]]:
    """Keep only DGS-relevant tabular files; drop dated duplicates within a group.

    Returns ``(included_paths, all_decisions)``. Skipped files are not opened.
    """

    decisions = [classify_dgs_relevance(path) for path in paths]
    included = [item for item in decisions if item.include]
    by_group: dict[str, list[DgsRelevanceDecision]] = {}
    for item in included:
        by_group.setdefault(item.group_key, []).append(item)

    selected: list[Path] = []
    final_decisions: list[DgsRelevanceDecision] = []
    seen_selected: set[str] = set()

    for item in decisions:
        if not item.include:
            final_decisions.append(item)
            continue
        group = by_group[item.group_key]
        if len(group) == 1:
            selected.append(item.path)
            final_decisions.append(item)
            seen_selected.add(str(item.path))
            continue
        winner = max(group, key=lambda d: _date_rank(d.path))
        if item.path == winner.path and str(item.path) not in seen_selected:
            selected.append(item.path)
            final_decisions.append(item)
            seen_selected.add(str(item.path))
        elif item.path != winner.path:
            final_decisions.append(
                DgsRelevanceDecision(
                    path=item.path,
                    include=False,
                    reason=(
                        f"duplicado fechado; se usa {winner.path.name} "
                        f"(grupo {item.group_key!r})"
                    ),
                    group_key=item.group_key,
                )
            )

    return tuple(selected), tuple(final_decisions)
