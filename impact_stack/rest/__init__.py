"""Useful wrappers for the requests library."""

import collections
import posixpath
import typing
import urllib.parse

import requests

from impact_stack.rest import exceptions, rest, utils

try:
    import flask
except ImportError:
    pass

if typing.TYPE_CHECKING:  # pragma: no cover
    import django.http
    import flask

    IncomingRequest = flask.Request | django.http.HttpRequest
else:
    IncomingRequest = typing.TypeVar("IncomingRequest")


def base_url_from_request(request: IncomingRequest):
    """Extract the base URL from a request."""
    if hasattr(request, "base_url"):
        url = request.base_url
    elif hasattr(request, "build_absolute_uri"):
        url = request.build_absolute_uri("/")
    else:
        raise TypeError(f"Unsupported request type: {type(request)}")
    return url[: url.find("/api") + 1] if "/api" in url else url


def auth_from_request(request: IncomingRequest):
    """Extract the auth header from a request."""
    try:
        auth_header = request.headers["Authorization"]
    except KeyError as exc:
        raise exceptions.RequestUnauthorized("No request header in incoming request.") from exc

    def auth(request: requests.PreparedRequest):
        """Copy the authorization header into outgoing requests."""
        request.headers["Authorization"] = auth_header
        return request

    return auth


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


class ClientFactoryBase:
    """Factory for Impact Stack API clients which don’t need app-to-app authentication."""

    @classmethod
    def from_app(cls, app=None):
        """Create a new instance using the current flask app’s config."""
        return cls.from_config((app or flask.current_app).config.get)

    @staticmethod
    def create_app_configs(config_getter):
        """Generate the app config from config variables."""
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
        return app_configs

    @classmethod
    def from_config(cls, config_getter):
        """Create a new factory from a config object."""
        return cls(
            config_getter("IMPACT_STACK_API_URL_PATTERN"),
            cls.create_app_configs(config_getter),
        )

    def __init__(self, base_url_pattern: str, app_configs):
        """Create a new client factory instance."""
        self.base_url_pattern = base_url_pattern
        self.app_configs = app_configs

    def url_for_owner(self, data_owner: str) -> str:
        """Get the base URL for the specified data owner."""
        return self.base_url_pattern.format(data_owner=data_owner)

    def client_for_owner(self, data_owner: str, *args, **kwargs) -> rest.Client:
        """Create a new API client."""
        return self.client(self.url_for_owner(data_owner), *args, **kwargs)

    def client(self, base_url, app_slug, api_version=None, auth=None) -> rest.Client:
        """Get the an app client for a specific base URL."""
        config = self.app_configs[app_slug]
        api_version = api_version or config["api_version"]
        path = posixpath.join("api", app_slug, api_version)
        if isinstance(client_class := config["class"], str):
            client_class = utils.class_from_path(client_class)
        return client_class(
            urllib.parse.urljoin(base_url, path),
            auth=auth,
            request_timeout=config["timeout"],
        )

    def forwarding(self, request: IncomingRequest, app_slug, api_version=None):
        """Get a new API client for forwarding requests to another Impact Stack app."""
        auth = auth_from_request(request)
        base_url = base_url_from_request(request)
        return self.client(base_url, app_slug, api_version, auth)


class ClientFactory(ClientFactoryBase):
    """Factory for Impact Stack API clients."""

    @staticmethod
    def timeout_sum(timeout):
        """Sum up all the values in a requests timeout."""
        # A timeout is a tuple of connect and read timeout. Passing an integer is a short hand for
        # using the same number for both.
        return timeout * 2 if isinstance(timeout, int) else sum(timeout)

    @classmethod
    def from_config(cls, config_getter):
        """Create a new factory from a config object."""
        return cls(
            config_getter("IMPACT_STACK_API_URL_PATTERN"),
            cls.create_app_configs(config_getter),
            config_getter("IMPACT_STACK_API_KEY"),
        )

    def __init__(self, base_url_pattern, app_configs, api_key):
        """Create a new client factory instance."""
        super().__init__(base_url_pattern, app_configs)
        self.auth_clients: dict[str, rest.Client] = {}
        self.api_key = api_key

    def get_middleware(self, base_url):
        """Get the auth middleware for the specified base URL."""
        if not base_url in self.auth_clients:
            self.auth_clients[base_url] = self.client(base_url, "auth")
        auth_client = self.auth_clients[base_url]
        return AuthMiddleware(
            auth_client, self.api_key, self.timeout_sum(auth_client.request_timeout)
        )

    def app_to_app(self, data_owner, app_slug, api_version=None) -> rest.Client:
        """Get a new API client for Impact Stack app to app requests."""
        base_url = self.url_for_owner(data_owner)
        auth = self.get_middleware(base_url)
        return self.client(base_url, app_slug, api_version, auth=auth)


Client = rest.Client
__all__ = [
    "AuthMiddleware",
    "ClientFactory",
    "ClientFactoryBase",
    "Client",
    "exceptions",
]
