from datetime import datetime, timezone

from app import clock


class _Frozen(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 11, 30, 23, 30, tzinfo=timezone.utc).astimezone(tz)


def test_today_is_local(monkeypatch):
    """23:30 UTC on 11-30 is 00:30 on 12-01 in Bratislava."""
    monkeypatch.setattr(clock, "datetime", _Frozen)
    assert clock.today() == "2026-12-01"
    assert clock.now_utc() == "2026-11-30T23:30:00Z"
