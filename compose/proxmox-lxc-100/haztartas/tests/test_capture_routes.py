import json
import re
import uuid

from sqlalchemy import func, select

from app import clock
from app.models import Entry
from helpers import add, cat, child_wallet, household, user
from app.strings.hu import S


def count(app):
    with app.state.db.session() as s:
        return s.scalar(select(func.count()).select_from(Entry))


def payload(app, **kw):
    """A queue item's payload as capture.js sends it: the form's text values
    plus client_uuid and the author the cached form was rendered for."""
    base = dict(kind="expense", amount="12,50", currency="EUR",
                date=clock.today(), merchant="Tesco", note="", payment="card",
                wallet_id=str(household(app)),
                category_id=str(cat(app, "Élelmiszer")),
                client_uuid=str(uuid.uuid4()))
    base.update(kw)
    return base


def test_sync_without_session_is_401_json(client, users):
    r = client.post("/capture/sync", json=payload(users))
    assert r.status_code == 401
    assert "location" not in r.headers
    assert r.headers["content-type"].startswith("application/json")
    # htmx or not: never the redirect require_user would give
    r2 = client.post("/capture/sync", json=payload(users),
                     headers={"HX-Request": "true"})
    assert r2.status_code == 401 and "location" not in r2.headers
    assert count(users) == 0


def test_sync_creates_entry(adult, users):
    p = payload(users)
    r = adult.post("/capture/sync", json=p)
    assert r.status_code == 200
    body = r.json()
    assert body["client_uuid"] == p["client_uuid"]
    assert body["status"] == "confirmed"
    anna = user(users, "anna").id   # outside: every session takes the write lock
    with users.state.db.session() as s:
        e = s.get(Entry, body["entry_id"])
        assert (e.amount_minor, e.merchant, e.client_uuid) == (
            1250, "Tesco", p["client_uuid"])
        assert e.created_by == anna


def test_sync_twice_one_entry(adult, users):
    p = payload(users)
    first = adult.post("/capture/sync", json=p)
    again = adult.post("/capture/sync", json=p)
    assert first.status_code == again.status_code == 200
    assert first.json() == again.json()
    assert count(users) == 1


def test_sync_twice_after_a_duplicate_one_draft(adult, users):
    # the retry must not find its own first upload as a duplicate either
    add(users, "bela", amount_minor=1250)
    p = payload(users)
    a = adult.post("/capture/sync", json=p).json()
    b = adult.post("/capture/sync", json=p).json()
    assert a == b and a["status"] == "draft"
    assert count(users) == 2


def test_sync_bad_amount_422_echoes_uuid(adult, users):
    p = payload(users, amount="abc")
    r = adult.post("/capture/sync", json=p)
    assert r.status_code == 422
    assert r.json()["client_uuid"] == p["client_uuid"]
    assert r.json()["error"] == S["amount_invalid"]
    big = payload(users, amount="99999999999")
    r2 = adult.post("/capture/sync", json=big)
    assert r2.status_code == 422 and r2.json()["client_uuid"] == big["client_uuid"]
    assert count(users) == 0


def test_sync_missing_rate_422_asks_for_rate(adult, users):
    p = payload(users, currency="HUF", amount="5000")
    r = adult.post("/capture/sync", json=p)
    assert r.status_code == 422
    assert r.json() == {"client_uuid": p["client_uuid"],
                        "error": S["rate_needed"], "needs_rate": True}
    ok = adult.post("/capture/sync", json=dict(p, manual_rate="400"))
    assert ok.status_code == 200 and count(users) == 1


def test_sync_missing_category_422(adult, users):
    p = payload(users, category_id="")
    r = adult.post("/capture/sync", json=p)
    assert r.status_code == 422
    assert r.json()["error"] == S["category_required"]


def test_sync_rejects_bad_body(adult, users):
    for bad in ({"amount": "1"}, {"client_uuid": "not-a-uuid"},
                {"client_uuid": 5}):
        r = adult.post("/capture/sync", json=dict(payload(users), **bad)
                       if "amount" not in bad else bad)
        assert r.status_code == 422, bad
    assert adult.post("/capture/sync", content=b"[1,2]",
                      headers={"content-type": "application/json"}
                      ).status_code == 422
    assert adult.post("/capture/sync", content=b"{nope",
                      headers={"content-type": "application/json"}
                      ).status_code == 422
    # absurd ids are a 422, not a 500
    r = adult.post("/capture/sync", json=payload(users, wallet_id="9" * 40))
    assert r.status_code == 422
    assert count(users) == 0


def test_sync_duplicate_becomes_draft(adult, adult2, users):
    add(users, "bela", amount_minor=1250, merchant="Lidl")
    p = payload(users, merchant="Kaufland")
    r = adult.post("/capture/sync", json=p)
    assert r.status_code == 200
    assert r.json()["status"] == "draft"
    with users.state.db.session() as s:
        assert s.get(Entry, r.json()["entry_id"]).status == "draft"
    assert "Kaufland" in adult.get("/drafts").text
    assert "Kaufland" not in adult.get("/entries").text


def test_sync_duplicate_in_child_wallet_stays_confirmed(child, users):
    # /drafts lists only household drafts and only to adults: a draft in the
    # child's wallet would be an entry nobody can ever see.
    w = child_wallet(users)
    add(users, "cili", wallet_id=w, amount_minor=1250)
    r = child.post("/capture/sync", json=payload(users, wallet_id=str(w)))
    assert r.status_code == 200 and r.json()["status"] == "confirmed"


def test_sync_child_household_duplicate_stays_confirmed(child, users):
    # /drafts is adult-only: a child's draft would be an entry nobody sees.
    add(users, "cili", amount_minor=1250)
    r = child.post("/capture/sync", json=payload(users, merchant="Kaufland"))
    assert r.status_code == 200 and r.json()["status"] == "confirmed"


def test_sync_hidden_duplicate_stays_confirmed(adult, adult2, users):
    # A hidden draft 404s for the other adult under /drafts: saved confirmed.
    add(users, "bela", amount_minor=1250)
    r = adult.post("/capture/sync", json=payload(users, hidden="1"))
    assert r.status_code == 200 and r.json()["status"] == "confirmed"


def test_sync_uuid_of_other_author_is_409(adult, adult2, users):
    p = payload(users)
    assert adult.post("/capture/sync", json=p).status_code == 200
    r = adult2.post("/capture/sync", json=p)
    assert r.status_code == 409
    assert r.json()["client_uuid"] == p["client_uuid"]
    assert count(users) == 1


def test_sync_item_queued_by_another_user_is_409(adult, adult2, users):
    # Anna queued it offline and logged out; Béla logs in on the same phone.
    # Uploading it as Béla would hand him Anna's (possibly secret) entry.
    p = payload(users, user_id=str(user(users, "anna").id), hidden="1")
    r = adult2.post("/capture/sync", json=p)
    assert r.status_code == 409
    assert r.json()["client_uuid"] == p["client_uuid"]
    assert r.json()["error"] == S["queue_other_user"]
    assert count(users) == 0
    assert adult.post("/capture/sync", json=p).status_code == 200


def test_sync_not_allowed_wallet_is_403_json(child, users):
    p = payload(users, kind="income",
                category_id=str(cat(users, "Fizetés", "income")))
    r = child.post("/capture/sync", json=p)
    assert r.status_code == 403
    assert r.json()["client_uuid"] == p["client_uuid"]
    assert count(users) == 0


def test_sync_same_origin_fetch_passes_csrf_guard(adult, users):
    p = payload(users)
    r = adult.post("/capture/sync", json=p, headers={
        "Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"})
    assert r.status_code == 200
    r2 = adult.post("/capture/sync", json=payload(users), headers={
        "Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"})
    assert r2.status_code == 403
    assert count(users) == 1


def test_capture_page_anonymous_goes_to_login(client, users):
    r = client.get("/capture")
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_capture_page_renders_form(adult, users):
    r = adult.get("/capture")
    assert r.status_code == 200
    html = r.text
    assert 'name="amount"' in html and 'name="category_id"' in html
    assert "data-capture" in html
    assert f'data-user="{user(users, "anna").id}"' in html
    assert "data-pending" in html and "data-login" in html
    assert 'href="/login"' in html
    assert 'name="manual_rate"' in html


def test_every_page_links_manifest_and_capture_js(client, adult, users):
    for page in (client.get("/login"), adult.get("/"), adult.get("/capture")):
        assert '<link rel="manifest" href="/manifest.webmanifest">' in page.text
        assert '<script src="/static/capture.js" defer></script>' in page.text
        assert 'id="queue-strings"' in page.text
        assert "apple-touch-icon" in page.text


def test_sw_served_from_root_with_js_type(client):
    r = client.get("/sw.js")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript")
    assert "/capture" in r.text
    # capture.js warms the same cache sw.js serves from: one name in both
    name = re.search(r"const CACHE = '(haztartas-v\d+)'", r.text).group(1)
    assert f"const CACHE = '{name}'" in client.get("/static/capture.js").text


def test_capture_js_served(client):
    r = client.get("/static/capture.js")
    assert r.status_code == 200
    assert "/capture/sync" in r.text


def test_manifest_served(client):
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/manifest+json")
    m = json.loads(r.text)
    assert m["name"] == m["short_name"] == "Háztartás"
    assert m["start_url"] == "/" and m["display"] == "standalone"
    assert m["background_color"] == m["theme_color"] == "#f3f1ec"
    assert m["lang"] == "hu"
    sizes = {i["sizes"] for i in m["icons"]}
    assert {"192x192", "512x512"} <= sizes
    for icon in m["icons"]:
        img = client.get(icon["src"])
        assert img.status_code == 200
        assert img.headers["content-type"] == "image/png"
        w, h = int.from_bytes(img.content[16:20], "big"), int.from_bytes(img.content[20:24], "big")
        assert f"{w}x{h}" == icon["sizes"]


def test_every_page_has_exactly_one_counter(client, adult, users):
    pages = [client.get("/login")] + [adult.get(p) for p in (
        "/", "/capture", "/entries", "/entries/new", "/drafts", "/pocket",
        "/settings")]
    for page in pages:
        assert page.status_code == 200, page.url
        assert page.text.count("data-pending") == 1, page.url


def test_queue_strings_reach_the_page(client):
    html = client.get("/login").text
    blob = html.split('id="queue-strings">', 1)[1].split("</script>", 1)[0]
    strings = json.loads(blob)
    for js, key in (("pending", "queue_pending"), ("refused", "queue_refused"),
                    ("login", "queue_login"), ("other_user", "queue_other_user"),
                    ("other_user_count", "queue_other_user_count"),
                    ("discard", "queue_discard"),
                    ("discard_confirm", "queue_discard_confirm"),
                    ("no_storage", "capture_no_storage")):
        assert strings[js] == S[key], key
