"""Every error the API can return, through the real app: same envelope, right code and status.

When you add an ErrorCode, add a case here: tests/test_error_policy.py fails until every
request-reachable code appears in this file.
"""

import logging

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import services
from app.errors import DomainInvariantError, ErrorCode
from app.integrations.nasa_power import BASE_URL
from app.main import create_app
from app.settings import DataMode

CR = {"lat": 10.0, "lon": -84.2}


def assert_error(r: httpx.Response, status: int, code: ErrorCode) -> dict:
    assert r.status_code == status, r.text
    body = r.json()
    assert set(body) == {"error"}
    err = body["error"]
    assert set(err) == {"code", "message", "details", "request_id"}
    assert err["code"] == code.value
    assert err["message"]
    assert isinstance(err["details"], dict)
    assert err["request_id"] == r.headers["X-Request-ID"]
    return err


@pytest.fixture
def lenient_client(config, env) -> TestClient:
    """Returns 500 responses instead of re-raising server errors into the test."""
    return TestClient(create_app(config=config, env=env), raise_server_exceptions=False)


# ---------------------------------------------------------------- 4xx: caller can fix it
def test_out_of_region(client):
    err = assert_error(
        client.post("/recommendations", json={"lat": 40.0, "lon": -3.7}),
        422,
        ErrorCode.OUT_OF_REGION,
    )
    assert err["details"]["bbox"] == [-86.0, 8.0, -82.5, 11.3]


def test_out_of_region_on_conditions(client):
    assert_error(
        client.get("/conditions", params={"lat": 40, "lon": 0}), 422, ErrorCode.OUT_OF_REGION
    )


def test_unknown_crop(client):
    err = assert_error(
        client.post("/recommendations", json={**CR, "crops": ["kale", "rice"]}),
        422,
        ErrorCode.UNKNOWN_CROP,
    )
    assert err["details"]["unknown"] == ["kale"]
    assert "rice" in err["details"]["available"]


def test_invalid_priorities(client):
    zero = {"water": 0, "soil": 0, "climate": 0}
    assert_error(
        client.post("/recommendations", json={**CR, "priorities": zero}),
        422,
        ErrorCode.INVALID_PRIORITIES,
    )


@pytest.mark.parametrize(
    ("body", "loc"),
    [
        ({"lat": 200, "lon": -84.2}, "body.lat"),
        ({"lon": -84.2}, "body.lat"),
        ({**CR, "cultivos": ["rice"]}, "body.cultivos"),
        ({**CR, "top_n": 0}, "body.top_n"),
        ({**CR, "crops": []}, "body.crops"),
    ],
)
def test_body_validation(client, body, loc):
    err = assert_error(client.post("/recommendations", json=body), 422, ErrorCode.VALIDATION_FAILED)
    assert loc in [f["loc"] for f in err["details"]["fields"]]


def test_malformed_json(client):
    r = client.post(
        "/recommendations", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert_error(r, 422, ErrorCode.VALIDATION_FAILED)


def test_query_validation(client):
    err = assert_error(
        client.get("/conditions", params={"lat": "abc"}), 422, ErrorCode.VALIDATION_FAILED
    )
    assert {f["loc"] for f in err["details"]["fields"]} == {"query.lat", "query.lon"}


def test_unknown_route(client):
    assert_error(client.get("/nope"), 404, ErrorCode.NOT_FOUND)


def test_wrong_method(client):
    r = client.get("/recommendations")
    assert_error(r, 405, ErrorCode.METHOD_NOT_ALLOWED)
    assert "POST" in r.headers["allow"]


# ---------------------------------------------------------------- 5xx from data sources
def test_cache_miss(make_client):
    err = assert_error(
        make_client(data_mode=DataMode.CACHED).post("/recommendations", json=CR),
        503,
        ErrorCode.CACHE_MISS,
    )
    assert err["details"] == {"source": "nasa_power"}
    assert "data_mode=live" in err["message"]


@respx.mock
def test_source_unavailable(make_client):
    respx.get(BASE_URL).mock(return_value=httpx.Response(500))
    err = assert_error(
        make_client(data_mode=DataMode.LIVE).post("/recommendations", json=CR),
        502,
        ErrorCode.SOURCE_UNAVAILABLE,
    )
    assert err["details"]["status"] == 500


@respx.mock
def test_source_bad_data(make_client):
    respx.get(BASE_URL).mock(return_value=httpx.Response(200, json={"unexpected": True}))
    assert_error(
        make_client(data_mode=DataMode.LIVE).post("/recommendations", json=CR),
        502,
        ErrorCode.SOURCE_BAD_DATA,
    )


# ---------------------------------------------------------------- 5xx bugs: never leak internals
def test_unexpected_exception_is_generic_500(lenient_client, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("secret-token-123 leaked?")

    monkeypatch.setattr(services, "recommend", boom)
    err = assert_error(
        lenient_client.post("/recommendations", json=CR), 500, ErrorCode.INTERNAL_ERROR
    )
    assert "secret" not in str(err)
    assert err["details"] == {}


def test_500_keeps_cors_headers(lenient_client, monkeypatch):
    """The browser must be able to read the envelope and request id of a crash."""

    def boom(*_a, **_k):
        raise RuntimeError("kaput")

    monkeypatch.setattr(services, "recommend", boom)
    origin = "http://localhost:5173"
    r = lenient_client.post("/recommendations", json=CR, headers={"Origin": origin})
    assert_error(r, 500, ErrorCode.INTERNAL_ERROR)
    assert r.headers["access-control-allow-origin"] == origin
    assert "x-request-id" in r.headers["access-control-expose-headers"].lower()


def test_internal_app_error_message_is_hidden(lenient_client, monkeypatch):
    def boom(*_a, **_k):
        raise DomainInvariantError("internal detail", details={"x": 1})

    monkeypatch.setattr(services, "recommend", boom)
    err = assert_error(
        lenient_client.post("/recommendations", json=CR), 500, ErrorCode.DOMAIN_INVARIANT
    )
    assert "internal detail" not in err["message"]
    assert err["details"] == {}


# ---------------------------------------------------------------- request id + logging
def test_request_id_is_echoed_when_safe(client):
    r = client.get("/nope", headers={"X-Request-ID": "front-abc.123"})
    assert r.json()["error"]["request_id"] == "front-abc.123"


def test_unsafe_request_id_is_replaced(client):
    r = client.get("/nope", headers={"X-Request-ID": "bad id\nwith newline"})
    assert r.json()["error"]["request_id"] != "bad id\nwith newline"


def test_success_responses_have_request_id(client):
    assert client.get("/health").headers["X-Request-ID"]


def test_client_errors_log_info_without_traceback(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.errors"):
        client.get("/nope")
    (rec,) = [r for r in caplog.records if r.name == "app.errors"]
    assert rec.levelno == logging.INFO
    assert rec.exc_info is None


def test_server_errors_log_error_with_traceback(lenient_client, monkeypatch, caplog):
    def boom(*_a, **_k):
        raise RuntimeError("kaput")

    monkeypatch.setattr(services, "recommend", boom)
    with caplog.at_level(logging.INFO, logger="app.errors"):
        lenient_client.post("/recommendations", json=CR)
    (rec,) = [r for r in caplog.records if r.name == "app.errors"]
    assert rec.levelno == logging.ERROR
    assert rec.exc_info is not None
