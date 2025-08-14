"""Tests for the client factory."""

import datetime
from unittest import mock

import django.http
import flask
import pytest

from impact_stack import rest


def test_base_url_from_request_flask():
    """Test that the base URL is extracted from flask requests."""
    request = mock.Mock(spec=flask.Request)
    request.base_url = "https://org.impact-stack.net/api/test/v1"
    assert rest.base_url_from_request(request) == "https://org.impact-stack.net/"


def test_base_url_from_request_django():
    """Test that the base URL is extracted from Django requests."""
    request = mock.Mock(spec=django.http.HttpRequest)
    request.build_absolute_uri.return_value = "https://org.impact-stack.net/"
    assert rest.base_url_from_request(request) == "https://org.impact-stack.net/"
    assert request.build_absolute_uri.mock_calls == [mock.call("/")]


def test_configs_used(app):
    """Test configs and default values used when creating client factories."""
    app.config = mock.Mock()
    config = {
        "IMPACT_STACK_API_URL_PATTERN": "https://{data_owner}.impact-stack.net",
    }
    app.config.get.side_effect = lambda k, default=None: config.get(k, default)
    rest.ClientFactoryBase.from_app()
    assert app.config.mock_calls == [
        mock.call.get("IMPACT_STACK_API_URL_PATTERN"),
        mock.call.get("IMPACT_STACK_API_CLIENT_DEFAULTS", {}),
        mock.call.get("IMPACT_STACK_API_CLIENT_CONFIG", {"auth": {"api_version": "v1"}}),
    ]
    app.config.reset_mock()

    rest.ClientFactory.from_app()
    assert app.config.mock_calls == [
        mock.call.get("IMPACT_STACK_API_URL_PATTERN"),
        mock.call.get("IMPACT_STACK_API_CLIENT_DEFAULTS", {}),
        mock.call.get("IMPACT_STACK_API_CLIENT_CONFIG", {"auth": {"api_version": "v1"}}),
        mock.call.get("IMPACT_STACK_API_KEY"),
    ]


@pytest.mark.usefixtures("app")
def test_override_class():
    """Test that the client class can be overridden on a per-app basis."""
    factory = rest.ClientFactory.from_app()

    test_client_cls = type("TestClient", (rest.rest.Client,), {})
    factory.app_configs["test"] = {**factory.app_configs["test"], **{"class": test_client_cls}}
    assert isinstance(factory.client_for_owner("org", "test", "v1"), test_client_cls)


@pytest.mark.usefixtures("app")
def test_class_from_path():
    """Test instantiating a client class by passing the class path as string."""
    factory = rest.ClientFactory.from_app()
    factory.app_configs["test"] = {
        **factory.app_configs["test"],
        **{"class": "impact_stack.rest.Client"},
    }
    assert isinstance(factory.client_for_owner("org", "test", "v1"), rest.Client)


@pytest.mark.usefixtures("app")
def test_override_timeout():
    """Test that clients can get specific default timeouts."""
    factory = rest.ClientFactory.from_app()
    test_client_cls = mock.Mock()
    factory.app_configs["test"] = {**factory.app_configs["test"], **{"class": test_client_cls}}
    factory.client_for_owner("org", "test", "v1")
    assert test_client_cls.mock_calls == [
        mock.call("https://org.impact-stack.net/api/test/v1", auth=None, request_timeout=2),
    ]
    test_client_cls.reset_mock()
    factory.app_configs["test"]["timeout"] = 42
    factory.client_for_owner("org", "test", "v1")
    assert test_client_cls.mock_calls == [
        mock.call("https://org.impact-stack.net/api/test/v1", auth=None, request_timeout=42),
    ]


@pytest.mark.usefixtures("app")
def test_forwarding_client(requests_mock):
    """Test that a forwarding client forwards the authorization header."""
    requests_mock.get("https://org.impact-stack.net/api/test/v1/", json={"status": "ok"})
    factory = rest.ClientFactory.from_app()

    incoming_request = mock.Mock(spec=flask.Request)
    incoming_request.base_url = "https://org.impact-stack.net/api/foo/v2"
    incoming_request.headers = {"Authorization": "Bearer JWT-token"}
    client = factory.client_forwarding(incoming_request, "test", "v1")
    assert client.get(json_response=True) == {"status": "ok"}
    assert "Authorization" in requests_mock.request_history[0].headers
    assert requests_mock.request_history[0].headers["Authorization"] == "Bearer JWT-token"

    incoming_request = mock.Mock(spec=flask.Request)
    incoming_request.base_url = "https://org.impact-stack.net/api/foo/v2"
    incoming_request.headers = {}
    with pytest.raises(rest.exceptions.RequestUnauthorized):
        factory.client_forwarding(incoming_request, "test", "v1")


@pytest.mark.usefixtures("app")
def test_forwarding_app_client(requests_mock):
    """Test that a forwarding app client uses the app token."""
    requests_mock.get("https://org.impact-stack.net/api/test/v1/", json={"status": "ok"})
    requests_mock.post(
        "https://org.impact-stack.net/api/auth/v1/token",
        json={"token": "app-token", "exp": datetime.datetime.now().timestamp() + 30},
    )
    factory = rest.ClientFactory.from_app()

    incoming_request = mock.Mock(spec=flask.Request)
    incoming_request.base_url = "https://org.impact-stack.net/api/foo/v2"
    incoming_request.headers = {"Authorization": "Bearer incoming-token"}
    client = factory.client_forwarding_as_app(incoming_request, "test", "v1")
    assert client.get(json_response=True) == {"status": "ok"}
    assert len(requests_mock.request_history) == 2
    assert "Authorization" in requests_mock.request_history[1].headers
    assert requests_mock.request_history[1].headers["Authorization"] == "Bearer app-token"
