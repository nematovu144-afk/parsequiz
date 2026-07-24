"""Domain-specific exceptions."""


class ParseError(Exception):
    """Raised when a document cannot be parsed at all."""


class UnsupportedFormatError(ParseError):
    """File extension is not supported."""


class CorruptedFileError(ParseError):
    """File exists but cannot be opened / decoded."""
