"""Auth middlewares for the requests library."""

import requests


class AuthAppMiddleware:
    """Middleware for authenticating using JWT tokens.

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
