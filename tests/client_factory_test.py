"""Tests for the client factory."""

from unittest import mock

import pytest

from impact_stack import rest


@pytest.mark.usefixtures("app")
def test_override_class():
    """Test that the client class can be overridden on a per-app basis."""
    factory = rest.ClientFactory.from_app()

    test_client_cls = type("TestClient", (rest.rest.Client,), {})
    factory.client_classes["test"] = test_client_cls
    assert isinstance(factory.get_client("test", "v1"), test_client_cls)


def test_override_timeout(app):
    """Test that clients can get specific default timeouts."""
    factory = rest.ClientFactory.from_app()
    test_client_cls = mock.Mock()
    factory.client_classes["test"] = test_client_cls
    factory.get_client("test", "v1", needs_auth=None)
    assert test_client_cls.mock_calls == [
        mock.call(app.config["IMPACT_STACK_API_URL"] + "/test/v1", auth=None, request_timeout=2),
    ]
    test_client_cls.reset_mock()
    factory.timeouts["test"] = 42
    factory.get_client("test", "v1", needs_auth=None)
    assert test_client_cls.mock_calls == [
        mock.call(app.config["IMPACT_STACK_API_URL"] + "/test/v1", auth=None, request_timeout=42),
    ]
