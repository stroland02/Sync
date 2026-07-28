"""An exception nothing catches by type, which is the ordinary case rather than a defect."""


class CannotPatch(Exception):
    """Raised by a tier that accepted a change and then found it could not act."""
