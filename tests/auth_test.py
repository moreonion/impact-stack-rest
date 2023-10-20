"""Unit-tests for the auth middleware implementations."""
# pylint: disable=too-few-public-methods

import datetime
from unittest import mock

import pytest
import requests_mock as rm

from impact_stack.rest import AuthMiddleware, ClientFactory


def test_auth_client(app, requests_mock):
    """Test getting a token from the client app."""
    client = ClientFactory.from_config(app.config.get).get_client("auth")
    token_response = {
        "token": "TOKEN.org1",
        "exp": datetime.datetime.now().timestamp() + 3600,
    }
    requests_mock.post(rm.ANY, json=token_response)
    token = client.post("token", json="api-key").json()["token"]
    assert token == "TOKEN.org1"
    assert len(requests_mock.request_history) == 1
    assert requests_mock.request_history[0].url == "https://impact-stack.net/api/auth/v1/token"
    assert requests_mock.request_history[0].json() == "api-key"


def test_client_with_middleware(app, requests_mock):
    """Test sending authorized requests."""
    client = ClientFactory.from_config(app.config.get).app_to_app("test", "v42")
    initial_time = datetime.datetime(2023, 9, 26, 13, 7)
    token_response = {
        "token": "TOKEN.org1",
        "exp": initial_time.timestamp() + 3600,
    }
    requests_mock.post("https://impact-stack.net/api/auth/v1/token", json=token_response)
    requests_mock.get("https://impact-stack.net/api/test/v42/answer", json={"answer": 42})
    with mock.patch("impact_stack.rest.utils.now", return_value=initial_time):
        assert client.get("answer", json_response=True) == {"answer": 42}
    assert len(requests_mock.request_history) == 2
    assert requests_mock.request_history[1].headers["Authorization"] == "Bearer TOKEN.org1"
    requests_mock.reset()

    # Test that the token is reused by the client when sending a second request.
    almost_time_to_reftesh = initial_time + datetime.timedelta(seconds=3600 - 5)
    with mock.patch("impact_stack.rest.utils.now", return_value=almost_time_to_reftesh):
        assert client.get("answer", json_response=True) == {"answer": 42}
    assert len(requests_mock.request_history) == 1
    assert requests_mock.request_history[0].headers["Authorization"] == "Bearer TOKEN.org1"
    requests_mock.reset()

    # Test that a new token is requested when there is less than half of its life time left.
    time_to_refresh = initial_time + datetime.timedelta(seconds=3600 - 3)
    with mock.patch("impact_stack.rest.utils.now", return_value=time_to_refresh):
        assert client.get("answer", json_response=True) == {"answer": 42}
    assert len(requests_mock.request_history) == 2


@pytest.mark.usefixtures("app")
def test_factory_instantiation_from_app():
    """Test getting a client factory from a flask app."""
    factory = ClientFactory.from_app()
    assert isinstance(factory.auth_middleware, AuthMiddleware)


def test_renewal_without_api_key(app, requests_mock):
    """Test that session renewal works without an API-key."""
    del app.config["IMPACT_STACK_API_KEY"]
    factory = ClientFactory.from_app()
    client = factory.get_client("auth")
    requests_mock.post("https://impact-stack.net/api/auth/v1/renew", json={"status": "ok"})
    assert client.post("renew", json_response=True) == {"status": "ok"}
