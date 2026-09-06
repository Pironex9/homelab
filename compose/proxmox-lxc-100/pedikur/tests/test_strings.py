"""User-facing copy lives in app/strings/hu.py, and it is accented Hungarian.

The templates carry markup and {{ S[...] }} lookups, nothing else, so any
non-ASCII character in a template is a Hungarian string that escaped the
strings file, where nobody translating or proofreading the app will find it.
"""
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_no_hardcoded_copy_in_templates():
    offenders = []
    for path in sorted(TEMPLATES.rglob("*.html")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if any(ord(ch) > 127 for ch in line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, (
        "non-ASCII text in a template means copy that bypassed "
        "app/strings/hu.py:\n" + "\n".join(offenders))


def test_the_strings_file_is_accented_hungarian():
    """A regression guard with teeth: these keys have no accent-free spelling,
    so an ASCII value here means someone typed the placeholder form."""
    from app.strings.hu import S

    must_be_accented = [
        "app_name", "login_title", "login_user", "login_password",
        "login_submit", "login_failed", "login_locked", "logout",
        "nav_calendar", "nav_more",
    ]
    plain = [k for k in must_be_accented
             if all(ord(ch) < 128 for ch in S[k])]
    assert not plain, f"unaccented Hungarian in app/strings/hu.py: {plain}"
