"""Useful wrappers for the requests library."""
import posixpath
import urllib.parse

from impact_stack.rest import auth, rest

try:
    import flask
except ImportError:  # pragma: no cover
    pass


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
        self.auth_middleware = auth.AuthAppMiddleware(
            self.get_client("auth", needs_auth=False),
            api_key,
        )

    def get_client(self, app_slug, api_version=None, needs_auth=True):
        """Get a new API client for an Impact Stack service."""
        api_version = api_version or self.DEFAULT_API_VERSIONS[app_slug]
        path = posixpath.join("api", app_slug, api_version)
        base_url = urllib.parse.urljoin(self.base_url, path)
        auth_ = self.auth_middleware if needs_auth else None
        return rest.Client(base_url, auth=auth_)
