class InputError(RuntimeError):
    """Base error raised by universal input adapters."""


class UnsupportedInputError(InputError):
    """Raised when no reader can handle an input source."""


class InputDependencyError(InputError):
    """Raised when an optional dependency required by a format is missing."""


class DatasetConflictError(InputError):
    """Raised when multiple sources expose the same logical table unexpectedly."""
