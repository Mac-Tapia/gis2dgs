class ElectricalLibraryError(ValueError):
    """Base error for electrical type-library operations."""


class DuplicateElectricalTypeError(ElectricalLibraryError):
    """Raised when a type identifier is added more than once."""


class UnknownElectricalTypeError(ElectricalLibraryError):
    """Raised when a requested type identifier is not in the library."""
