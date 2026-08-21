class PowerFactoryMappingError(ValueError):
    """Raised when the canonical network cannot be mapped safely to PowerFactory."""


class DuplicatePowerFactoryObjectError(PowerFactoryMappingError):
    """Raised when a stable foreign key is generated more than once."""


class DanglingPowerFactoryReferenceError(PowerFactoryMappingError):
    """Raised when a mapped object references an object that does not exist."""
