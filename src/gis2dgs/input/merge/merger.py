from __future__ import annotations

from collections.abc import Iterable

from ..dataset import InputDataset


def merge_datasets(
    datasets: Iterable[InputDataset],
    *,
    on_conflict: str = "error",
) -> InputDataset:
    """Merge source datasets with one copy per input table.

    The implementation mutates only the newly-created result instead of
    repeatedly copying the full accumulated dataset. This keeps merge cost
    linear in the number of tables and avoids quadratic memory churn when a
    project combines many files or database views.
    """
    result = InputDataset()
    for dataset in datasets:
        for table in dataset.tables.values():
            result.add_table(
                table.name,
                table.frame,
                source_id=table.source_id,
                metadata=table.metadata,
                on_conflict=on_conflict,
            )
    return result
