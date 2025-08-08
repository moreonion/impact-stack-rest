"""Tests for the client factory."""

from unittest import mock

import pytest

from impact_stack import rest


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
    assert isinstance(factory.get_client("org", "test", "v1"), test_client_cls)


@pytest.mark.usefixtures("app")
def test_class_from_path():
    """Test instantiating a client class by passing the class path as string."""
    factory = rest.ClientFactory.from_app()
    factory.app_configs["test"] = {
        **factory.app_configs["test"],
        **{"class": "impact_stack.rest.Client"},
    }
    assert isinstance(factory.get_client("org", "test", "v1"), rest.Client)


@pytest.mark.usefixtures("app")
def test_override_timeout():
    """Test that clients can get specific default timeouts."""
    factory = rest.ClientFactory.from_app()
    test_client_cls = mock.Mock()
    factory.app_configs["test"] = {**factory.app_configs["test"], **{"class": test_client_cls}}
    factory.get_client("org", "test", "v1")
    assert test_client_cls.mock_calls == [
        mock.call("https://org.impact-stack.net/api/test/v1", auth=None, request_timeout=2),
    ]
    test_client_cls.reset_mock()
    factory.app_configs["test"]["timeout"] = 42
    factory.get_client("org", "test", "v1")
    assert test_client_cls.mock_calls == [
        mock.call("https://org.impact-stack.net/api/test/v1", auth=None, request_timeout=42),
    ]


@pytest.mark.usefixtures("app")
def test_forwarding_client(requests_mock):
    """Test that a forwarding client forwards the authorization header."""
    requests_mock.get("https://org.impact-stack.net/api/test/v1/", json={"status": "ok"})
    factory = rest.ClientFactory.from_app()

    incoming_request = mock.Mock()
    incoming_request.base_url = "https://org.impact-stack.net/api/foo/v2"
    incoming_request.headers = {"Authorization": "Bearer JWT-token"}
    client = factory.forwarding(incoming_request, "test", "v1")
    assert client.get(json_response=True) == {"status": "ok"}
    assert "Authorization" in requests_mock.request_history[0].headers
    assert requests_mock.request_history[0].headers["Authorization"] == "Bearer JWT-token"

    incoming_request = mock.Mock()
    incoming_request.headers = {}
    with pytest.raises(rest.exceptions.RequestUnauthorized):
        factory.forwarding(incoming_request, "test", "v1")
