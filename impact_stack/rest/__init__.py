"""Useful wrappers for the requests library."""
import collections
import datetime
import posixpath
import urllib.parse

import requests

from impact_stack.rest import exceptions, rest, utils

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
            self.expires_at = data["exp"]
        return self.token

    def __call__(self, request: requests.PreparedRequest):
        """Add the JWT token to the request."""
        request.headers["Authorization"] = "Bearer " + self.get_token()
        return request


class ClientFactory:
    """Factory for Impact Stack API clients."""

    @staticmethod
    def timeout_sum(timeout):
        """Sum up all the values in a requests timeout."""
        # A timeout is a tuple of connect and read timeout. Passing an integer is a short hand for
        # using the same number for both.
        return timeout * 2 if isinstance(timeout, int) else sum(timeout)

    @classmethod
    def from_app(cls, app=None):
        """Create a new instance using the current flask app’s config."""
        return cls.from_config((app or flask.current_app).config.get)

    @classmethod
    def from_config(cls, config_getter):
        """Create a new factory from a config object."""
        app_defaults = {
            **{"class": rest.Client, "timeout": 2},
            **config_getter("IMPACT_STACK_API_CLIENT_DEFAULTS", {}),
        }
        app_overrides = config_getter("IMPACT_STACK_API_CLIENT_CONFIG", {})
        app_overrides.setdefault("auth", {"api_version": "v1"})
        app_configs = collections.defaultdict(lambda: app_defaults)
        app_configs.update(
            {app: {**app_defaults, **overrides} for app, overrides in app_overrides.items()}
        )
        return cls(
            config_getter("IMPACT_STACK_API_URL"),
            config_getter("IMPACT_STACK_API_KEY"),
            app_configs,
        )

    def __init__(self, base_url, api_key, app_configs):
        """Create a new client factory instance."""
        self.base_url = base_url
        self.app_configs = app_configs
        auth_client = self.get_client("auth")
        self.auth_middleware = AuthMiddleware(
            auth_client,
            api_key,
            self.timeout_sum(auth_client.request_timeout),
        )

    def get_client(self, app_slug, api_version=None, auth=None):
        """Create a new API client."""
        config = self.app_configs[app_slug]
        api_version = api_version or config["api_version"]
        path = posixpath.join("api", app_slug, api_version)
        if isinstance(client_class := config["class"], str):
            client_class = utils.class_from_path(client_class)
        return client_class(
            urllib.parse.urljoin(self.base_url, path),
            auth=auth,
            request_timeout=config["timeout"],
        )

    def app_to_app(self, app_slug, api_version=None):
        """Get a new API client for Impact Stack app to app requests."""
        return self.get_client(app_slug, api_version, self.auth_middleware)

    def forwarding(self, incoming_request, app_slug, api_version=None):
        """Get a new API client for forwarding requests to another Impact Stack app."""
        try:
            auth_header = incoming_request.headers["Authorization"]
        except KeyError as exc:
            raise exceptions.RequestUnauthorized("No request header in incoming request.") from exc

        def auth(request: requests.PreparedRequest):
            """Copy the authorization header into outgoing requests."""
            request.headers["Authorization"] = auth_header
            return request

        return self.get_client(app_slug, api_version, auth)


Client = rest.Client
__all__ = [
    "AuthMiddleware",
    "ClientFactory",
    "Client",
    "exceptions",
]
