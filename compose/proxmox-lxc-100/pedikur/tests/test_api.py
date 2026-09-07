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
    httpx will not encode a str header like this, but it passes bytes through
    verbatim, so the whole route path is exercised rather than the helper."""
    r = client.get("/api/clients",
                   headers={"Authorization": b"Bearer caf\xe9"})
    assert r.status_code == 401


@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/clients", None),
    ("get", "/api/treatments", None),
    ("get", "/api/visits?from=2026-09-01&to=2026-09-02", None),
    ("post", "/api/clients", {"name": "x"}),
    ("post", "/api/visits", {"client_id": 1, "starts_at": "2026-09-10T10:00",
                             "treatment_ids": [1]}),
])
def test_every_endpoint_refuses_a_request_without_a_token(client, method, path,
                                                          body):
    """Every 401 assertion used to target /api/clients, so deleting the guard
    from a write endpoint left the suite green."""
    call = getattr(client, method)
    r = call(path) if body is None else call(path, json=body)
    assert r.status_code == 401, path
    assert r.headers["www-authenticate"] == "Bearer"


def test_a_missing_query_parameter_is_still_a_401_without_a_token(client):
    """FastAPI validates query parameters before it calls a handler, so an
    in-handler check answered 422 and named the interface to a caller who had
    presented nothing."""
    assert client.get("/api/visits").status_code == 401
    assert client.post("/api/clients", content=b"{oops").status_code == 401


def test_a_lowercase_bearer_scheme_is_accepted(api):
    assert api.get("/api/clients",
                   headers={"Authorization": "bearer test-token"}).status_code == 200


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


@pytest.mark.parametrize("payload", [
    {"name": "x", "phone": {"a": 1}},
    {"name": "x", "phone": ["0900"]},
    {"name": "x", "phone": 123},
])
def test_a_phone_that_is_not_a_string_is_a_400(api, payload):
    """name was type checked and phone was not, so a dict reached the bind
    parameter and raised out of sqlite3 as something no handler caught."""
    assert api.post("/api/clients", headers=TOKEN, json=payload).status_code == 400


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
    # arbitrary precision JSON integers pass int() and then overflow at bind
    ({"client_id": 2 ** 70, "starts_at": "2026-09-10T10:00",
      "treatment_ids": [1]}, 400),
    ({"client_id": 1, "starts_at": "2026-09-10T10:00",
      "treatment_ids": [2 ** 70]}, 400),
    # a bare string would iterate into [1, 2]: two bookings from one typo
    ({"client_id": 1, "starts_at": "2026-09-10T10:00",
      "treatment_ids": "12"}, 400),
    ({"client_id": 0, "starts_at": "2026-09-10T10:00", "treatment_ids": [1]}, 400),
])
def test_a_bad_visit_payload_never_500s(api, payload, code):
    assert api.post("/api/visits", headers=TOKEN, json=payload).status_code == code


def test_a_visit_created_over_the_api_is_recorded_as_api(api):
    r = api.post("/api/visits", headers=TOKEN, json={
        "client_id": 1, "starts_at": "2026-09-10T10:00", "treatment_ids": [1]})
    assert isinstance(r.json()["id"], int)
    from app.models import Visit
    with api.app.state.db.session() as s:
        assert s.get(Visit, r.json()["id"]).created_by == "api"


def test_the_total_is_an_integer_over_several_lines(api):
    api.post("/settings/treatments",
             data={"name": "Géllakk", "duration_min": "30",
                   "price_eur": "18,33"})
    api.post("/api/visits", headers=TOKEN, json={
        "client_id": 1, "starts_at": "2026-09-10T10:00",
        "treatment_ids": [1, 2]})
    body = api.get("/api/visits?from=2026-09-10&to=2026-09-11",
                   headers=TOKEN).json()
    assert body[0]["total_cents"] == 2500 + 1833
    assert isinstance(body[0]["total_cents"], int)


def test_an_erased_clients_name_does_not_come_back_through_their_visits(api):
    api.post("/visits/new", data={
        "client_id": "1", "start": "2026-09-10T10:00", "end": "",
        "treatment_ids": ["1"]})
    assert api.get("/api/visits?from=2026-09-10&to=2026-09-11",
                   headers=TOKEN).json() != []
    from app.models import Client
    with api.app.state.db.session() as s:
        s.get(Client, 1).erased_at = "2026-09-11T10:00:00Z"
    assert api.get("/api/visits?from=2026-09-10&to=2026-09-11",
                   headers=TOKEN).json() == []


def test_there_is_no_erase_endpoint(api):
    """The only irreversible operation in the system, and no machine use case
    needs it."""
    assert api.delete("/api/clients/1", headers=TOKEN).status_code in (404, 405)
    assert api.post("/api/clients/1/erase", headers=TOKEN).status_code == 404
    assert api.delete("/api/visits/1", headers=TOKEN).status_code in (404, 405)
