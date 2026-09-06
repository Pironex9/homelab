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
        # a unique name per call: duplicate treatment names are refused
        treatment = treatments.create(s, f"Kezelés {client.id}", minutes, 2500,
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


def test_the_grid_widens_to_hold_a_visit_that_runs_past_closing(db):
    """Clamping it onto the last row would draw it at a time it does not
    happen, and below 45 minutes the block shows no time of its own to
    contradict the row it sits on."""
    _book(db, datetime(2026, 9, 7, 16, 30, tzinfo=timeutil.LOCAL), minutes=120)
    with db.session() as s:
        grid = schedule.week_grid(s, date(2026, 9, 7))
        assert grid.end_min == 18 * 60 + 30
        block = grid.days[0].blocks[0]
        assert block.row_span == 8               # 120 minutes, not truncated
        assert block.row_start + block.row_span - 1 == grid.rows


def test_the_grid_widens_to_hold_a_visit_before_opening(db):
    _book(db, datetime(2026, 9, 7, 8, 0, tzinfo=timeutil.LOCAL), minutes=90)
    with db.session() as s:
        grid = schedule.week_grid(s, date(2026, 9, 7))
        assert grid.start_min == 8 * 60
        block = grid.days[0].blocks[0]
        assert block.row_start == 1
        assert block.row_span == 6               # all 90 minutes are on screen


def test_a_visit_entirely_outside_the_working_day_keeps_its_own_time(db):
    """The one the clamping got wrong: 18:00 on a day that closes at 17:00 was
    drawn on the 16:45 row, on top of whatever really was at 16:45."""
    _book(db, datetime(2026, 9, 7, 16, 45, tzinfo=timeutil.LOCAL), minutes=15,
          name="Korán")
    _book(db, datetime(2026, 9, 7, 18, 0, tzinfo=timeutil.LOCAL), minutes=60,
          name="Későn")
    with db.session() as s:
        grid = schedule.week_grid(s, date(2026, 9, 7))
        early, late = sorted(grid.days[0].blocks, key=lambda b: b.row_start)
        assert early.row_start != late.row_start
        assert late.row_start == early.row_start + 5    # 16:45 to 18:00


def test_a_no_show_is_still_drawn(db):
    """A past day where nobody turned up would otherwise render as if nothing
    had ever been booked."""
    visit = _book(db, datetime(2026, 9, 7, 10, 0, tzinfo=timeutil.LOCAL))
    with db.session() as s:
        visits.set_status(s, visit.id, "no_show")
    with db.session() as s:
        blocks = schedule.week_grid(s, date(2026, 9, 7)).days[0].blocks
        assert [b.status for b in blocks] == ["no_show"]


def test_a_soft_deleted_visit_is_not_drawn(db):
    visit = _book(db, datetime(2026, 9, 7, 10, 0, tzinfo=timeutil.LOCAL))
    with db.session() as s:
        from app.models import Visit
        s.get(Visit, visit.id).deleted_at = "2026-09-06T10:00:00Z"
    with db.session() as s:
        assert schedule.week_grid(s, date(2026, 9, 7)).days[0].blocks == []


def test_the_block_carries_its_treatment_names(db):
    _book(db, datetime(2026, 9, 7, 10, 0, tzinfo=timeutil.LOCAL), minutes=45)
    with db.session() as s:
        assert schedule.week_grid(s, date(2026, 9, 7)).days[0].blocks[0].label \
            == "Kezelés 1"


def test_the_week_window_holds_its_first_and_last_minute(db):
    """>= and < at the two ends: nothing dropped, nothing counted twice."""
    _book(db, datetime(2026, 9, 7, 0, 0, tzinfo=timeutil.LOCAL), minutes=30,
          name="Elso")
    _book(db, datetime(2026, 9, 13, 23, 30, tzinfo=timeutil.LOCAL), minutes=30,
          name="Utolso")
    _book(db, datetime(2026, 9, 14, 0, 0, tzinfo=timeutil.LOCAL), minutes=30,
          name="Kovetkezo")
    with db.session() as s:
        grid = schedule.week_grid(s, date(2026, 9, 7))
        assert [b.client_name for b in grid.days[0].blocks] == ["Elso"]
        assert [b.client_name for b in grid.days[6].blocks] == ["Utolso"]
        assert sum(len(d.blocks) for d in grid.days) == 2
    with db.session() as s:
        nxt = schedule.week_grid(s, date(2026, 9, 14))
        assert [b.client_name for b in nxt.days[0].blocks] == ["Kovetkezo"]


def test_two_visits_an_hour_apart_on_the_autumn_sunday_do_not_stack(db):
    """2026-10-25: 02:30 local happens twice, so two Visits an hour apart in
    real time share a wall clock and would land on the same row."""
    from app.models import WorkingHours
    with db.session() as s:
        s.add(WorkingHours(date="2026-10-25", start="00:00", end="23:45",
                           is_closed=0))
    _book(db, datetime(2026, 10, 25, 1, 30, tzinfo=timeutil.LOCAL), minutes=30,
          name="Elotte")
    _book(db, datetime(2026, 10, 25, 4, 0, tzinfo=timeutil.LOCAL), minutes=30,
          name="Utana")
    with db.session() as s:
        sunday = schedule.week_grid(s, date(2026, 10, 19)).days[6]
        rows = sorted(b.row_start for b in sunday.blocks)
        assert len(rows) == 2
        assert rows[0] != rows[1]


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
