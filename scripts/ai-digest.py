#!/usr/bin/env python3
"""Napi AI digest: FreshRSS -> claude -p -> markdown + Telegram.

A feedek lekérését, dedupe-ját és tárolását a FreshRSS végzi (LXC 100, :8083),
ez a script csak olvassa a GReader API-t. Feedet a FreshRSS UI-ban adj hozzá,
az "AI" vagy "AI Video" kategóriába - itt nincs feed-lista.
A szűrés minőségét a prompt.md adja, nem ez a kód. Azt tuningold.
"""
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

FRESHRSS = "http://192.168.0.110:8083/api/greader.php"
KARAKEEP = "http://192.168.0.128:3000/api/v1"
CATEGORIES = {"AI": 300, "AI Video": 100}
OUT_DIR = "/root/homelab/private/ai-digest"
PROMPT_FILE = f"{OUT_DIR}/prompt.md"
STATE_FILE = f"{OUT_DIR}/.last-run"
MAX_LOOKBACK_H = 36  # ha rég futott, ennél régebbre nem megyünk vissza
TG_LIMIT = 4000      # a Telegram limit 4096, hagyunk ráhagyást
# A Telegram csak ezeket a tageket fogadja el, minden más 400-as hibát ad.
TG_TAGS = "b|strong|i|em|u|s|strike|del|a|code|pre|blockquote|tg-spoiler"


def secret(name):
    with open(f"/root/.secrets/{name}") as f:
        return f.read().strip()


def get(url, auth=None):
    req = urllib.request.Request(url)
    if auth:
        req.add_header("Authorization", f"GoogleLogin auth={auth}")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode()


def login():
    q = urllib.parse.urlencode({"Email": "nex", "Passwd": secret("freshrss-api-key")})
    for line in get(f"{FRESHRSS}/accounts/ClientLogin?{q}").splitlines():
        if line.startswith("Auth="):
            return line[5:]
    raise SystemExit("FreshRSS login sikertelen")


def clean(text, limit):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def fetch(auth, since):
    """Az AI kategóriák since óta megjelent tételei, forrás szerint csoportosítva."""
    items = []
    for cat, n in CATEGORIES.items():
        url = (f"{FRESHRSS}/reader/api/0/stream/contents/user/-/label/"
               f"{urllib.parse.quote(cat)}?n={n}&ot={since}&output=json")
        for it in json.loads(get(url, auth)).get("items", []):
            ts = it.get("published", 0)
            if ts < since:  # az ot-ra nem hagyatkozunk vakon
                continue
            video = cat == "AI Video"
            items.append({
                "ts": ts,
                "video": video,
                "source": it["origin"]["title"],
                "title": clean(it["title"], 200),
                "url": it.get("canonical", [{}])[0].get("href", ""),
                "text": clean(it.get("summary", {}).get("content", ""), 200 if video else 700),
            })
    items.sort(key=lambda i: i["ts"], reverse=True)
    return items


def render_input(items):
    lines = []
    for i in items:
        kind = "VIDEÓ" if i["video"] else "CIKK"
        when = datetime.fromtimestamp(i["ts"], timezone.utc).strftime("%m-%d %H:%M")
        lines.append(f"[{kind}] [{i['source']}] [{when}] {i['title']}\n{i['url']}\n{i['text']}\n")
    return "\n".join(lines)


def sanitize_html(text):
    """Ismeretlen tagek kidobása, hogy a Telegram ne 400-azzon el egy egész napot.

    A modell a tiltás ellenére is szeret felvezetni ("Íme a digest:"), ezért az
    első <b> előtti fecsegést levágjuk - ezt olcsóbb kódban kezelni, mint promptban.
    """
    text = re.sub(rf"</?(?!({TG_TAGS})\b)[a-zA-Z][^>]*>", "", text)
    start = text.find("<b>")
    return text[start:] if start > 0 else text


def split_chunks(text, limit=TG_LIMIT):
    chunks, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > limit:
            if cur:
                chunks.append(cur)
            cur = line[:limit]
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        chunks.append(cur)
    return chunks


def telegram(text):
    try:
        token, chat = secret("telegram-bot").split("\n")[0], secret("telegram-bot").split("\n")[1]
    except (FileNotFoundError, IndexError):
        print("! /root/.secrets/telegram-bot hiányzik vagy hibás (1. sor: token, 2. sor: chat_id)"
              " - a digest csak fájlba került", file=sys.stderr)
        return
    for chunk in split_chunks(text):
        for mode in ("HTML", None):  # ha a HTML megfekszik, inkább nyersen menjen ki
            body = {"chat_id": chat, "text": chunk, "disable_web_page_preview": "true"}
            if mode:
                body["parse_mode"] = mode
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=urllib.parse.urlencode(body).encode())
            try:
                with urllib.request.urlopen(req, timeout=30):
                    break
            except Exception as e:
                print(f"! Telegram ({mode}): {e}", file=sys.stderr)


def kept_urls(digest, items):
    """A digestben linkelt tételek = amit a modell megtartott.

    Nem kérünk külön listát a modelltől: amire linkelt, az a döntése.
    """
    linked = set(re.findall(r'<a href="([^"]+)"', digest))
    return [i for i in items if i["url"] in linked]


def archive(items, day):
    """A megtartott tételek a Karakeepbe: link + oldal-pillanatkép + címke."""
    try:
        key = secret("karakeep-api-key")
    except FileNotFoundError:
        return 0
    saved = 0
    for i in items:
        try:
            body = json.dumps({"type": "link", "url": i["url"], "title": i["title"]}).encode()
            req = urllib.request.Request(f"{KARAKEEP}/bookmarks", data=body, method="POST")
            req.add_header("Authorization", f"Bearer {key}")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=30) as r:
                bid = json.load(r)["id"]
            tags = json.dumps({"tags": [{"tagName": "ai-digest"}, {"tagName": day}]}).encode()
            req = urllib.request.Request(f"{KARAKEEP}/bookmarks/{bid}/tags", data=tags, method="POST")
            req.add_header("Authorization", f"Bearer {key}")
            req.add_header("Content-Type", "application/json")
            urllib.request.urlopen(req, timeout=30).close()
            saved += 1
        except Exception as e:
            print(f"! Karakeep ({i['url']}): {e}", file=sys.stderr)
    return saved


def main():
    now = int(time.time())
    try:
        with open(STATE_FILE) as f:
            since = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        since = now - 24 * 3600
    since = max(since, now - MAX_LOOKBACK_H * 3600)

    items = fetch(login(), since)
    if not items:
        print("Nincs új tétel, kihagyva.")
        return

    with open(PROMPT_FILE) as f:
        prompt = f.read()

    result = subprocess.run(
        ["claude", "-p", "--model", "sonnet", prompt],
        input=render_input(items), capture_output=True, text=True, timeout=900)
    if result.returncode != 0:
        raise SystemExit(f"claude hiba: {result.stderr[:500]}")

    digest = sanitize_html(result.stdout.strip())
    day = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(OUT_DIR, exist_ok=True)
    path = f"{OUT_DIR}/{day}.md"
    with open(path, "w") as f:
        f.write(f"# AI digest {day}\n\n_{len(items)} tétel {MAX_LOOKBACK_H}h ablakból_\n\n{digest}\n")

    telegram(digest)
    saved = archive(kept_urls(digest, items), day)
    with open(STATE_FILE, "w") as f:
        f.write(str(now))
    print(f"{len(items)} tétel -> {path}, {saved} a Karakeepbe")


def selftest():
    assert clean("<p>a &amp;  b</p>", 99) == "a & b"
    assert sanitize_html("<h2>x</h2><b>y</b><a href='u'>z</a>") == "<b>y</b><a href='u'>z</a>"
    assert sanitize_html("Íme a digest:\n<b>cím</b>") == "<b>cím</b>"
    assert sanitize_html("<b>cím</b> szöveg") == "<b>cím</b> szöveg"  # nem vág, ha elöl van
    assert split_chunks("a\nb\nc", limit=3) == ["a\nb", "c"]
    assert len(split_chunks("x" * 50, limit=10)) == 1  # a limitnél hosszabb sor nem vész el
    its = [{"url": "https://a.hu", "title": "a"}, {"url": "https://b.hu", "title": "b"}]
    assert [i["url"] for i in kept_urls('<a href="https://b.hu">x</a>', its)] == ["https://b.hu"]
    assert kept_urls("<b>semmi link</b>", its) == []
    long = "\n".join("y" * 30 for _ in range(400))
    assert all(len(c) <= TG_LIMIT for c in split_chunks(long))
    assert "".join(split_chunks(long)).replace("\n", "") == long.replace("\n", "")
    print("selftest OK")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
