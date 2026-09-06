"""The display filters every price and date on every screen goes through."""
import pytest

from app.display import eur
from app.services.timeutil import localdate


@pytest.mark.parametrize("cents,text", [
    (2500, "25,00 EUR"),
    (0, "0,00 EUR"),
    (5, "0,05 EUR"),
    (1250, "12,50 EUR"),
    (100000, "1000,00 EUR"),
    # Python floors towards minus infinity: -150 // 100 is -2 and -150 % 100
    # is 50, so the naive version renders minus one fifty as "-2,50 EUR".
    # Nothing writes a negative price today; the dashboard result and stock
    # corrections in phase 2 will.
    (-150, "-1,50 EUR"),
    (-5, "-0,05 EUR"),
    (-2500, "-25,00 EUR"),
])
def test_eur(cents, text):
    assert eur(cents) == text


@pytest.mark.parametrize("cents,text", [
    # SQLite hands a SUM() back as a float and a nullable column as None, and
    # neither may turn a whole page into a 500 on the way to a price
    (2500.0, "25,00 EUR"),
    (None, "0,00 EUR"),
])
def test_eur_survives_what_sqlite_actually_returns(cents, text):
    assert eur(cents) == text


@pytest.mark.parametrize("iso,text", [
    # A naive string means the writer forgot the Z. Treating it as container
    # local time would make it silently correct-looking and an hour or two
    # wrong; every late evening visit would land on the previous day.
    ("2026-09-01T23:30:00", "2026. 09. 02."),
    ("2026-09-01T07:00:00Z", "2026. 09. 01."),
    # 23:30 UTC is already the next day in Bratislava, summer or winter
    ("2026-09-01T23:30:00Z", "2026. 09. 02."),
    ("2026-01-01T23:30:00Z", "2026. 01. 02."),
    ("2026-09-01T07:00:00+00:00", "2026. 09. 01."),
])
def test_localdate_converts_out_of_utc(iso, text):
    assert localdate(iso) == text
