"""Define custom exception classes."""


class RequestUnauthorized(ValueError):
    """Exception raised for attempts to create forwarding clients from unauthorized requests."""
