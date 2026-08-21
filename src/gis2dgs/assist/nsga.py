from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from random import Random

ObjectiveVector = tuple[float, ...]


def dominates(left: ObjectiveVector, right: ObjectiveVector) -> bool:
    at_least_one_better = False
    for left_value, right_value in zip(left, right, strict=True):
        if left_value < right_value:
            return False
        if left_value > right_value:
            at_least_one_better = True
    return at_least_one_better


def fast_non_dominated_sort(objectives: list[ObjectiveVector]) -> list[list[int]]:
    size = len(objectives)
    dominated_count = [0] * size
    dominates_set: list[list[int]] = [[] for _ in range(size)]
    fronts: list[list[int]] = [[]]
    for left in range(size):
        for right in range(size):
            if left == right:
                continue
            if dominates(objectives[left], objectives[right]):
                dominates_set[left].append(right)
            elif dominates(objectives[right], objectives[left]):
                dominated_count[left] += 1
        if dominated_count[left] == 0:
            fronts[0].append(left)
    index = 0
    while fronts[index]:
        nxt: list[int] = []
        for left in fronts[index]:
            for right in dominates_set[left]:
                dominated_count[right] -= 1
                if dominated_count[right] == 0:
                    nxt.append(right)
        index += 1
        fronts.append(nxt)
    return [front for front in fronts if front]


def crowding_distances(objectives: list[ObjectiveVector], front: list[int]) -> dict[int, float]:
    distances = {index: 0.0 for index in front}
    if len(front) <= 2:
        for index in front:
            distances[index] = float("inf")
        return distances
    width = len(objectives[0])
    for axis in range(width):
        ordered = sorted(front, key=lambda index: objectives[index][axis])
        distances[ordered[0]] = float("inf")
        distances[ordered[-1]] = float("inf")
        span = objectives[ordered[-1]][axis] - objectives[ordered[0]][axis]
        if span == 0:
            continue
        for position in range(1, len(ordered) - 1):
            previous_value = objectives[ordered[position - 1]][axis]
            next_value = objectives[ordered[position + 1]][axis]
            distances[ordered[position]] += (next_value - previous_value) / span
    return distances


@dataclass(frozen=True, slots=True)
class NsgaResult:
    population: list[list[int]]
    objectives: list[ObjectiveVector]
    fronts: list[list[int]]


def nsga_ii(
    evaluate: Callable[[list[int]], ObjectiveVector],
    randomize: Callable[[Random], list[int]],
    crossover: Callable[[Random, list[int], list[int]], list[int]],
    mutate: Callable[[Random, list[int]], list[int]],
    *,
    population_size: int = 32,
    generations: int = 24,
    seed: int = 42,
    crossover_rate: float = 0.9,
    mutation_rate: float = 0.25,
) -> NsgaResult:
    """Compact NSGA-II. Chromosomes are integer vectors; all objectives are maximized."""

    rng = Random(seed)
    population = [randomize(rng) for _ in range(population_size)]
    objectives = [evaluate(chromosome) for chromosome in population]

    for _ in range(generations):
        offspring: list[list[int]] = []
        while len(offspring) < population_size:
            first = population[rng.randrange(population_size)]
            second = population[rng.randrange(population_size)]
            child = crossover(rng, first, second) if rng.random() < crossover_rate else list(first)
            if rng.random() < mutation_rate:
                child = mutate(rng, child)
            offspring.append(child)
        combined = population + offspring
        combined_obj = objectives + [evaluate(chromosome) for chromosome in offspring]
        fronts = fast_non_dominated_sort(combined_obj)
        next_pop: list[list[int]] = []
        next_obj: list[ObjectiveVector] = []
        for front in fronts:
            if len(next_pop) + len(front) <= population_size:
                for index in front:
                    next_pop.append(combined[index])
                    next_obj.append(combined_obj[index])
                continue
            distances = crowding_distances(combined_obj, front)
            ranked = sorted(front, key=lambda index: distances[index], reverse=True)
            for index in ranked:
                if len(next_pop) >= population_size:
                    break
                next_pop.append(combined[index])
                next_obj.append(combined_obj[index])
            break
        population = next_pop
        objectives = next_obj

    return NsgaResult(population, objectives, fast_non_dominated_sort(objectives))
