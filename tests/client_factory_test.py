"""Tests for the client factory."""

import pytest

from impact_stack import rest


@pytest.mark.usefixtures("app")
def test_override_class():
    """Test that the client class can be overridden on a per-app basis."""
    factory = rest.ClientFactory.from_app()

    test_client_cls = type("TestClient", (rest.rest.Client,), {})
    factory.client_classes["test"] = test_client_cls
    assert isinstance(factory.get_client("test", "v1"), test_client_cls)
