"""The internal JSON surface.

Not reachable through Pangolin: the reverse proxy denies /api/*. The token is
the second layer, because the app does not trust a proxy config to be right,
including its own deny rule.
"""
import pytest

TOKEN = {"Authorization": "Bearer test-token"}


@pytest.fixture
def api(logged_in):
    logged_in.post("/clients", data={"name": "Kovács Anna", "phone": "0900"})
    logged_in.post("/settings/treatments",
                   data={"name": "Pedikűr", "duration_min": "45",
                         "price_eur": "25,00"})
    return logged_in


def test_api_requires_a_bearer_token(client):
    assert client.get("/api/clients").status_code == 401
    assert client.get("/api/clients",
                      headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/clients",
                      headers={"Authorization": "test-token"}).status_code == 401


def test_a_non_ascii_token_is_refused_not_a_500(client):
    """compare_digest raises TypeError on a non-ASCII str, and Starlette
    decodes headers as latin-1, so raw bytes on the wire produce exactly that.
    httpx refuses to encode such a header client side, so the guard is called
    directly rather than through a request that cannot be made."""
    from fastapi import HTTPException

    from app.routers import api

    with pytest.raises(HTTPException) as raised:
        api._authorise(_FakeRequest(client), "Bearer café")
    assert raised.value.status_code == 401


class _FakeRequest:
    def __init__(self, client):
        self.app = client.app


def test_api_returns_json_with_a_valid_token(client):
    res = client.get("/api/clients", headers=TOKEN)
    assert res.status_code == 200
    assert res.json() == []


def test_health_needs_no_token(client):
    assert client.get("/health").status_code == 200


def test_clients_never_carry_the_alert_wording(api):
    api.post("/clients/1", data={
        "name": "Kovács Anna", "phone": "0900", "email": "", "address": "",
        "alert": "cukorbeteg", "notes": ""})
    body = api.get("/api/clients", headers=TOKEN).json()
    assert body == [{"id": 1, "name": "Kovács Anna", "phone": "0900",
                     "has_alert": True}]


def test_treatments_list_prices_in_integer_cents(api):
    body = api.get("/api/treatments", headers=TOKEN).json()
    assert body[0]["price_cents"] == 2500
    assert isinstance(body[0]["price_cents"], int)


def test_visits_are_filtered_by_a_local_date_range(api):
    api.post("/visits/new", data={
        "client_id": "1", "start": "2026-09-10T10:00", "end": "",
        "treatment_ids": ["1"]})
    res = api.get("/api/visits?from=2026-09-10&to=2026-09-11", headers=TOKEN)
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["client"] == "Kovács Anna"
    assert body[0]["starts_at"] == "2026-09-10T08:00:00Z"
    assert body[0]["treatments"] == ["Pedikűr"]
    # money stays an integer: qty is REAL, so the naive product is a float
    assert body[0]["total_cents"] == 2500
    assert isinstance(body[0]["total_cents"], int)

    assert api.get("/api/visits?from=2026-09-11&to=2026-09-12",
                   headers=TOKEN).json() == []


def test_a_malformed_date_range_is_a_400_not_a_500(api):
    r = api.get("/api/visits?from=tegnap&to=2026-09-11", headers=TOKEN)
    assert r.status_code == 400


def test_creating_a_client_over_the_api_records_it_as_api(api):
    r = api.post("/api/clients", headers=TOKEN, json={"name": "Új Kliens"})
    assert r.status_code == 201
    from app.models import Client
    with api.app.state.db.session() as s:
        assert s.get(Client, r.json()["id"]).created_by == "api"


def test_a_client_payload_without_a_name_is_a_400(api):
    assert api.post("/api/clients", headers=TOKEN, json={}).status_code == 400
    assert api.post("/api/clients", headers=TOKEN,
                    json={"name": "  "}).status_code == 400


def test_creating_a_visit_over_the_api(api):
    r = api.post("/api/visits", headers=TOKEN, json={
        "client_id": 1, "starts_at": "2026-09-10T10:00", "treatment_ids": [1]})
    assert r.status_code == 201
    r = api.post("/api/visits", headers=TOKEN, json={
        "client_id": 1, "starts_at": "2026-09-10T10:15", "treatment_ids": [1]})
    assert r.status_code == 409


@pytest.mark.parametrize("payload,code", [
    ({}, 400),
    ({"client_id": 1, "starts_at": "tegnap", "treatment_ids": [1]}, 400),
    ({"client_id": 999, "starts_at": "2026-09-10T10:00", "treatment_ids": [1]}, 404),
    ({"client_id": 1, "starts_at": "2026-09-10T10:00", "treatment_ids": [999]}, 404),
    ({"client_id": 1, "starts_at": "2026-09-10T10:00", "treatment_ids": []}, 400),
])
def test_a_bad_visit_payload_never_500s(api, payload, code):
    assert api.post("/api/visits", headers=TOKEN, json=payload).status_code == code


def test_there_is_no_erase_endpoint(api):
    """The only irreversible operation in the system, and no machine use case
    needs it."""
    assert api.delete("/api/clients/1", headers=TOKEN).status_code in (404, 405)
    assert api.post("/api/clients/1/erase", headers=TOKEN).status_code == 404
    assert api.delete("/api/visits/1", headers=TOKEN).status_code in (404, 405)
