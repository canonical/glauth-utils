class UtilityError(Exception):
    """Base class for custom errors."""


class InvalidDistinguishedNameError(UtilityError):
    """Error for invalid distinguished name."""


class InvalidAttributeValueError(UtilityError):
    """Error for invalid attribute value."""
