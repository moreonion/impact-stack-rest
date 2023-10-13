"""Tests for the client factory."""

from unittest import mock

import pytest

from impact_stack import rest


@pytest.mark.usefixtures("app")
def test_override_class():
    """Test that the client class can be overridden on a per-app basis."""
    factory = rest.ClientFactory.from_app()

    test_client_cls = type("TestClient", (rest.rest.Client,), {})
    factory.app_configs["test"] = {**factory.app_configs["test"], **{"class": test_client_cls}}
    assert isinstance(factory.get_client("test", "v1"), test_client_cls)


@pytest.mark.usefixtures("app")
def test_class_from_path():
    """Test instantiating a client class by passing the class path as string."""
    factory = rest.ClientFactory.from_app()
    factory.app_configs["test"] = {
        **factory.app_configs["test"],
        **{"class": "impact_stack.rest.Client"},
    }
    assert isinstance(factory.get_client("test", "v1"), rest.Client)


def test_override_timeout(app):
    """Test that clients can get specific default timeouts."""
    factory = rest.ClientFactory.from_app()
    test_client_cls = mock.Mock()
    factory.app_configs["test"] = {**factory.app_configs["test"], **{"class": test_client_cls}}
    factory.get_client("test", "v1")
    assert test_client_cls.mock_calls == [
        mock.call(app.config["IMPACT_STACK_API_URL"] + "/test/v1", auth=None, request_timeout=2),
    ]
    test_client_cls.reset_mock()
    factory.app_configs["test"]["timeout"] = 42
    factory.get_client("test", "v1")
    assert test_client_cls.mock_calls == [
        mock.call(app.config["IMPACT_STACK_API_URL"] + "/test/v1", auth=None, request_timeout=42),
    ]


@pytest.mark.usefixtures("app")
def test_forwarding_client(requests_mock):
    """Test that a forwarding client forwards the authorization header."""
    requests_mock.get("https://impact-stack.net/api/test/v1/", json={"status": "ok"})
    factory = rest.ClientFactory.from_app()

    incoming_request = mock.Mock()
    incoming_request.headers = {"Authorization": "Bearer JWT-token"}
    client = factory.forwarding(incoming_request, "test", "v1")
    assert client.get(json_response=True) == {"status": "ok"}
    assert "Authorization" in requests_mock.request_history[0].headers
    assert requests_mock.request_history[0].headers["Authorization"] == "Bearer JWT-token"

    incoming_request = mock.Mock()
    incoming_request.headers = {}
    with pytest.raises(rest.exceptions.RequestUnauthorized):
        factory.forwarding(incoming_request, "test", "v1")
