"""Useful wrappers for the requests library."""
import collections
import datetime
import posixpath
import urllib.parse

import requests

from impact_stack.rest import rest, utils

try:
    import flask
except ImportError:  # pragma: no cover
    pass


class AuthMiddleware:
    """Requests middleware for authenticating using JWT tokens.

    The middleware transparently requests an API-token from the auth-app during the first request.
    Afterwards each request gets the token added to its headers.

    A new token is requested on-demand whenever the old token has (almost) expired.
    """

    def __init__(self, client, api_key, token_life_time_buffer):
        """Create new auth-app requests auth middleware."""
        self.client = client
        self.api_key = api_key
        self.life_time_buffer = token_life_time_buffer
        self.token = None
        self.expires_at = None

    def needs_refresh(self):
        """Check if we have a token and it can still be used."""
        if not self.token:
            return True
        time_left = self.expires_at - utils.now().timestamp()
        return time_left < self.life_time_buffer

    def get_token(self):
        """Use the API key to get a JWT."""
        if self.needs_refresh():
            data = self.client.post("token", json=self.api_key, json_response=True)
            self.token = data["token"]
            self.expires_at = data["data"]["exp"]
        return self.token

    def __call__(self, request: requests.PreparedRequest):
        """Add the JWT token to the request."""
        request.headers["Authorization"] = "Bearer " + self.get_token()
        return request


def timeout_sum(timeout):
    """Sum up all the values in a requests timeout."""
    # A timeout is a tuple of connect and read timeout. Passing an integer is a short hand for
    # using the same number for both.
    return timeout * 2 if isinstance(timeout, int) else sum(timeout)


class ClientFactory:
    """Factory for Impact Stack API clients."""

    DEFAULT_API_VERSIONS = {
        "auth": "v1",
    }
    DEFAULT_CLASS = rest.Client
    DEFAULT_TIMEOUT = 2

    @classmethod
    def from_app(cls, app=None):
        """Create a new instance using the current flask app’s config."""
        return cls.from_config((app or flask.current_app).config.get)

    @classmethod
    def from_config(cls, config_getter):
        """Create a new factory from a config object."""
        return cls(config_getter("IMPACT_STACK_API_URL"), config_getter("IMPACT_STACK_API_KEY"))

    def __init__(self, base_url, api_key):
        """Create a new client factory instance."""
        self.base_url = base_url
        self.client_classes = collections.defaultdict(lambda: self.DEFAULT_CLASS)
        self.timeouts = collections.defaultdict(lambda: self.DEFAULT_TIMEOUT)
        auth_client = self.get_client("auth", needs_auth=False)
        self.auth_middleware = AuthMiddleware(
            auth_client,
            api_key,
            timeout_sum(auth_client.request_timeout),
        )

    def get_client(self, app_slug, api_version=None, needs_auth=True):
        """Get a new API client for an Impact Stack service."""
        api_version = api_version or self.DEFAULT_API_VERSIONS[app_slug]
        path = posixpath.join("api", app_slug, api_version)
        return self.client_classes[app_slug](
            urllib.parse.urljoin(self.base_url, path),
            auth=self.auth_middleware if needs_auth else None,
            request_timeout=self.timeouts[app_slug],
        )
