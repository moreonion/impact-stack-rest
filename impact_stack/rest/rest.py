"""Helpers for handling REST-APIs."""

import functools
import urllib.parse

import requests


class Client:
    """A General purpose REST / JSON API-client."""

    def __init__(self, base_url: str, auth=None, request_timeout=2):
        """Create a new API client instance."""
        self.request_timeout = request_timeout
        self._session = requests.Session()
        if auth:
            self._session.auth = auth
        if not base_url.endswith("/"):
            base_url += "/"
        self._base_url = base_url

    def __getattr__(self, name):
        """All undefined attributes are interpreted as HTTP verbs."""
        verb = name.upper()
        return functools.partial(self.request, verb)

    def request(self, method, *path_parts, path=None, url=None, json_response=False, **kwargs):
        """Send a request to the API-endpoint and handle the response.

        This accepts either of (the first of these wins):
        - A url passed as kwarg.
        - A path passed as kwarg.
        - Path parts that will be escaped and joined passed as positional arguments.
        """
        if path is None:
            path = "/".join(urllib.parse.quote_plus(part) for part in path_parts)
        if url:
            if not url.startswith(self._base_url):
                raise requests.URLRequired(f"This client only sends requests to {self._base_url}")
        else:
            url = self._base_url + path
        kwargs.setdefault("timeout", self.request_timeout)
        response = self._session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json() if json_response else response

    def __del__(self):
        """Close the session."""
        self._session.close()
