from __future__ import annotations

import math
from collections.abc import Sequence


def topsis_select(
    objectives: Sequence[tuple[float, ...]],
    weights: Sequence[float],
) -> int:
    """Pick the alternative closest to the ideal on a Pareto-style front.

    All objectives are treated as benefits (higher is better).
    """

    if not objectives:
        raise ValueError("TOPSIS requires at least one alternative.")
    width = len(objectives[0])
    if len(weights) != width:
        raise ValueError("TOPSIS weights must match objective count.")
    if abs(sum(weights) - 1.0) > 1e-6:
        raise ValueError("TOPSIS weights must sum to 1.")

    columns = list(zip(*objectives, strict=True))
    norms = [math.sqrt(sum(value * value for value in column)) or 1.0 for column in columns]
    weighted = [
        tuple(weights[index] * row[index] / norms[index] for index in range(width))
        for row in objectives
    ]
    ideal = tuple(max(row[index] for row in weighted) for index in range(width))
    nadir = tuple(min(row[index] for row in weighted) for index in range(width))

    def distance(row: tuple[float, ...], target: tuple[float, ...]) -> float:
        return math.sqrt(sum((row[index] - target[index]) ** 2 for index in range(width)))

    scores = []
    for row in weighted:
        to_ideal = distance(row, ideal)
        to_nadir = distance(row, nadir)
        scores.append(to_nadir / (to_ideal + to_nadir) if (to_ideal + to_nadir) else 0.0)
    return max(range(len(scores)), key=lambda index: scores[index])
