"""Unit-tests for the auth middleware implementations."""
# pylint: disable=too-few-public-methods

import flask
import pytest
import requests_mock as rm

from impact_stack.rest import ClientFactory, auth


@pytest.fixture(name="app", scope="class")
def fixture_app():
    """Define a test Flask app."""
    app = flask.Flask("test-app")
    app.config["IMPACT_STACK_API_URL"] = "https://impact-stack.net/api"
    app.config["IMPACT_STACK_API_KEY"] = "api-key"
    with app.app_context():
        yield app


def test_auth_client(app, requests_mock):
    """Test getting a token from the client app."""
    client = ClientFactory.from_config(app.config.get).get_client("auth", needs_auth=False)
    requests_mock.post(rm.ANY, json={"token": "TOKEN.org1"})
    token = client.post("token", json="api-key").json()["token"]
    assert token == "TOKEN.org1"
    assert len(requests_mock.request_history) == 1
    assert requests_mock.request_history[0].url == "https://impact-stack.net/api/auth/v1/token"
    assert requests_mock.request_history[0].json() == "api-key"


def test_client_with_middleware(app, requests_mock):
    """Test sending authorized requests."""
    client = ClientFactory.from_config(app.config.get).get_client("test", "v42")
    requests_mock.post("https://impact-stack.net/api/auth/v1/token", json={"token": "TOKEN.org1"})
    requests_mock.get("https://impact-stack.net/api/test/v42/answer", json={"answer": 42})
    assert client.get("answer", json_response=True) == {"answer": 42}
    assert len(requests_mock.request_history) == 2
    assert requests_mock.request_history[1].headers["Authorization"] == "Bearer TOKEN.org1"


@pytest.mark.usefixtures("app")
def test_factory_instantiation_from_app():
    """Test getting a client factory from a flask app."""
    factory = ClientFactory.from_app()
    assert isinstance(factory.auth_middleware, auth.AuthAppMiddleware)
