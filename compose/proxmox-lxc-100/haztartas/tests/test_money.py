import pytest

from app.clock import scheduled_day
from app.money import fmt_money, parse_amount


@pytest.mark.parametrize("text,minor", [
    ("12,50", 1250), ("12.50", 1250), ("12,5", 1250), ("12", 1200),
    ("1 200", 120000), ("1200", 120000), ("1.200,50", 120050), (" 7 ", 700),
    ("1.200", 120000)])
def test_parse_amount_accepts(text, minor):
    assert parse_amount(text) == minor


@pytest.mark.parametrize("text", [
    "", "abc", "-3", "0", "1,2,3", "12,345", "0,00", "12,", "0.500", "0.125"])
def test_parse_amount_rejects(text):
    with pytest.raises(ValueError):
        parse_amount(text)


def test_fmt_money_huf_has_no_decimals():
    assert fmt_money(120000, "HUF") == "1 200 Ft"


def test_fmt_money_eur():
    assert fmt_money(1250, "EUR") == "12,50 EUR"
    assert fmt_money(120050, "EUR") == "1 200,50 EUR"


def test_fmt_money_negative():
    assert fmt_money(-150, "EUR") == "-1,50 EUR"
    assert fmt_money(-340, "EUR") == "-3,40 EUR"


def test_scheduled_day_clamps():
    assert scheduled_day("2026-02", 31) == "2026-02-28"
    assert scheduled_day("2028-02", 31) == "2028-02-29"
    assert scheduled_day("2026-04", 31) == "2026-04-30"
    assert scheduled_day("2026-04", 5) == "2026-04-05"


def test_fmt_money_huf_keeps_fractional_part():
    assert fmt_money(12050, "HUF") == "120,50 Ft"
    assert fmt_money(-12050, "HUF") == "-120,50 Ft"


def test_fmt_eur_short_rounds_to_whole_euros():
    from app.money import fmt_eur_short
    assert fmt_eur_short(31249) == "312 €"
    assert fmt_eur_short(31250) == "313 €"
    assert fmt_eur_short(128450) == "1 285 €"
    assert fmt_eur_short(0) == "0 €"
    assert fmt_eur_short(-1450) == "-15 €"


def test_parse_amount_ceiling():
    import pytest
    from app.money import parse_amount
    assert parse_amount("9999999999,99") == 999999999999
    with pytest.raises(ValueError):
        parse_amount("9" * 30)
    with pytest.raises(ValueError):
        parse_amount("10000000000,01")
