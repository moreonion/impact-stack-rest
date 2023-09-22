"""Useful wrappers for the requests library."""
import posixpath
import urllib.parse

import requests

from impact_stack.rest import rest

try:
    import flask
except ImportError:  # pragma: no cover
    pass


class AuthMiddleware:
    """Requests middleware for authenticating using JWT tokens.

    The middleware transparently requests an API-token from the auth-app on-demand.
    """

    # pylint: disable=too-few-public-methods
    # For now the middleware is very simple, but in the future it should also take care of caching
    # the JWT and renew if needed.

    def __init__(self, client, api_key):
        """Create new auth-app requests auth middleware."""
        self.client = client
        self.api_key = api_key

    def get_token(self):
        """Use the API key to get a JWT."""
        return self.client.post("token", json=self.api_key, json_response=True)["token"]

    def __call__(self, request: requests.PreparedRequest):
        """Add the JWT token to the request."""
        request.headers["Authorization"] = "Bearer " + self.get_token()
        return request


class ClientFactory:
    """Factory for Impact Stack API clients."""

    DEFAULT_API_VERSIONS = {
        "auth": "v1",
    }

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
        self.auth_middleware = AuthMiddleware(self.get_client("auth", needs_auth=False), api_key)

    def get_client(self, app_slug, api_version=None, needs_auth=True):
        """Get a new API client for an Impact Stack service."""
        api_version = api_version or self.DEFAULT_API_VERSIONS[app_slug]
        path = posixpath.join("api", app_slug, api_version)
        base_url = urllib.parse.urljoin(self.base_url, path)
        auth_ = self.auth_middleware if needs_auth else None
        return rest.Client(base_url, auth=auth_)
