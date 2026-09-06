from datetime import date, datetime

import pytest

from app import migrate
from app.db import Database
from app.services import clients, schedule, timeutil, treatments, visits


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


def _book(db, when, minutes=45, name="Kovács Anna", alert=None):
    with db.session() as s:
        client = clients.create(s, name, None, created_by="1", alert=alert)
        treatment = treatments.create(s, f"Kezelés {minutes}", minutes, 2500,
                                      created_by="1")
        return visits.book(s, client.id, when, [treatment.id], created_by="1")


def test_seeded_week_is_open_monday_to_friday(db):
    with db.session() as s:
        assert schedule.hours_for(s, date(2026, 9, 7)).is_closed is False   # Mon
        assert schedule.hours_for(s, date(2026, 9, 12)) is None             # Sat


def test_date_override_beats_the_weekday_default(db):
    from app.models import WorkingHours
    with db.session() as s:
        s.add(WorkingHours(date="2026-09-09", start="00:00", end="00:00",
                           is_closed=1))
    with db.session() as s:
        assert schedule.hours_for(s, date(2026, 9, 9)).is_closed is True


def test_visit_lands_on_the_right_grid_rows(db):
    _book(db, datetime(2026, 9, 7, 10, 0, tzinfo=timeutil.LOCAL))
    with db.session() as s:
        grid = schedule.week_grid(s, date(2026, 9, 7))
        monday = grid.days[0]
        assert grid.start_min == 9 * 60          # seeded 09:00
        assert len(monday.blocks) == 1
        block = monday.blocks[0]
        assert block.row_start == 5              # 10:00 is four 15-min slots in
        assert block.row_span == 3               # 45 minutes
        assert block.client_name == "Kovács Anna"


def test_the_weekend_columns_are_closed_and_empty(db):
    with db.session() as s:
        grid = schedule.week_grid(s, date(2026, 9, 7))
        assert [d.is_closed for d in grid.days] == [False] * 5 + [True] * 2
        assert grid.rows == (17 - 9) * 60 // schedule.SLOT_MIN


def test_a_visit_running_past_closing_stops_at_the_last_row(db):
    """A span that overflows makes CSS grid invent rows, and the column then
    renders taller than every other one."""
    _book(db, datetime(2026, 9, 7, 16, 30, tzinfo=timeutil.LOCAL), minutes=120)
    with db.session() as s:
        grid = schedule.week_grid(s, date(2026, 9, 7))
        block = grid.days[0].blocks[0]
        assert block.row_start + block.row_span - 1 == grid.rows


def test_a_visit_starting_before_opening_starts_at_the_first_row(db):
    _book(db, datetime(2026, 9, 7, 8, 0, tzinfo=timeutil.LOCAL), minutes=90)
    with db.session() as s:
        grid = schedule.week_grid(s, date(2026, 9, 7))
        block = grid.days[0].blocks[0]
        assert block.row_start == 1
        assert block.row_span == 2               # only 09:00-09:30 is on screen


def test_the_alert_dot_travels_but_the_wording_does_not(db):
    _book(db, datetime(2026, 9, 7, 10, 0, tzinfo=timeutil.LOCAL),
          alert="cukorbeteg")
    with db.session() as s:
        block = schedule.week_grid(s, date(2026, 9, 7)).days[0].blocks[0]
        assert block.has_alert is True
        assert "cukorbeteg" not in repr(block)


def test_cancelled_visits_are_not_drawn(db):
    visit = _book(db, datetime(2026, 9, 7, 10, 0, tzinfo=timeutil.LOCAL))
    with db.session() as s:
        visits.set_status(s, visit.id, "cancelled")
    with db.session() as s:
        assert schedule.week_grid(s, date(2026, 9, 7)).days[0].blocks == []


def test_a_week_with_every_day_closed_still_renders(db):
    """min() over an empty sequence, and rows == 0 would make the grid
    template collapse to nothing."""
    from app.models import WorkingHours
    with db.session() as s:
        for row in s.query(WorkingHours):
            row.is_closed = 1
    with db.session() as s:
        grid = schedule.week_grid(s, date(2026, 9, 7))
        assert grid.rows > 0
        assert all(d.is_closed for d in grid.days)
