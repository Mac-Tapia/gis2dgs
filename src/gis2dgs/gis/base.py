from abc import ABC, abstractmethod

from .dataset import GisDataset


class GisReader(ABC):
    """Port for GIS data sources.

    Readers only extract GIS layers. They do not create electrical domain objects.
    That responsibility belongs to the normalization/mapping phase.
    """

    @abstractmethod
    def read(self) -> GisDataset:
        raise NotImplementedError
