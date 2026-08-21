class DgsError(Exception):
    """Base error for DGS conversion."""


class DgsSchemaNotConfiguredError(DgsError):
    """Raised when the DGS schema has not been configured."""


class DgsMappingError(DgsError):
    """Raised when semantic PowerFactory data cannot be mapped safely to DGS."""


class DgsTemplateError(DgsError):
    """Raised when the DGS workbook template is missing or incompatible."""
