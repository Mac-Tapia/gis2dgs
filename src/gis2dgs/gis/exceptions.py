class GisError(Exception):
    """Base error for GIS adapter failures."""


class GisLayerNotFoundError(GisError):
    pass


class GisSchemaError(GisError):
    pass


class GisMappingError(GisError):
    """A GIS row cannot be converted to the canonical electrical model."""


class GisConnectivityError(GisError):
    """Spatial connectivity inference cannot be performed safely."""
