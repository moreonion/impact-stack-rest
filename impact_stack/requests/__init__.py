"""Useful wrappers for the requests library."""

# Also provide exceptions to make them available with a single import.
from requests import exceptions, sessions  # pylint: disable=unused-import

from . import auth

Session = sessions.Session
__all__ = ["auth", "exceptions", "Session"]
