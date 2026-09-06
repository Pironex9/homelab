from datetime import datetime, timezone

import pytest

from app import migrate
from app.db import Database
from app.services import clients, timeutil, treatments, visits


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


@pytest.fixture
def fixtures(db):
    with db.session() as s:
        client = clients.create(s, "Kovács Anna", None, created_by="1")
        ped = treatments.create(s, "Pedikűr", 45, 2500, created_by="1")
        gel = treatments.create(s, "Géllakk", 30, 1800, created_by="1")
        return {"client_id": client.id, "ped": ped.id, "gel": gel.id}


def _local(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timeutil.LOCAL)


def _elapsed_minutes(visit) -> float:
    """Both ends carry the same tzinfo object, and Python subtracts those as
    wall clock, not as elapsed time. Across a DST transition that answers 90
    minutes for a 30 minute Visit. Convert first, subtract second."""
    start = timeutil.from_utc_iso(visit.starts_at).astimezone(timezone.utc)
    end = timeutil.from_utc_iso(visit.ends_at).astimezone(timezone.utc)
    return (end - start).total_seconds() / 60


def test_utc_conversion_survives_the_dst_change(db):
    # Europe/Bratislava springs forward on 2027-03-28.
    before = timeutil.to_utc_iso(_local(2027, 3, 27, 9))
    after = timeutil.to_utc_iso(_local(2027, 3, 28, 9))
    assert before.startswith("2027-03-27T08:00")   # CET, UTC+1
    assert after.startswith("2027-03-28T07:00")    # CEST, UTC+2
    # and back again
    assert timeutil.from_utc_iso(after).hour == 9


def test_stored_instants_all_have_the_same_shape(db, fixtures):
    """Mixed "+00:00" and "Z" in one column breaks every comparison: '+' sorts
    below 'Z', so an ORDER BY or a BETWEEN silently skips half the rows. The
    schema default writes the Z form, so to_utc_iso has to as well."""
    assert timeutil.to_utc_iso(_local(2026, 9, 10, 10)).endswith("Z")
    with db.session() as s:
        visit = visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                            [fixtures["ped"]], created_by="1")
        assert visit.starts_at.endswith("Z")
        assert visit.ends_at.endswith("Z")
        assert visit.created_at.endswith("Z")


def test_ends_at_is_the_summed_duration(db, fixtures):
    with db.session() as s:
        visit = visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                            [fixtures["ped"], fixtures["gel"]], created_by="1")
        assert timeutil.from_utc_iso(visit.ends_at) == _local(2026, 9, 10, 11, 15)


def test_manual_ends_at_wins_and_is_not_shrunk_by_a_new_treatment(db, fixtures):
    with db.session() as s:
        visit = visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                            [fixtures["ped"]], created_by="1",
                            ends_at_local=_local(2026, 9, 10, 12))
        assert timeutil.from_utc_iso(visit.ends_at) == _local(2026, 9, 10, 12)
        visits.add_treatment(s, visit.id, fixtures["gel"])
        # 45 + 30 = 75 minutes fits inside the manual window, so it stays
        assert timeutil.from_utc_iso(visit.ends_at) == _local(2026, 9, 10, 12)


def test_ends_at_grows_when_the_sum_exceeds_it(db, fixtures):
    with db.session() as s:
        visit = visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                            [fixtures["ped"]], created_by="1")
        visits.add_treatment(s, visit.id, fixtures["gel"])
        assert timeutil.from_utc_iso(visit.ends_at) == _local(2026, 9, 10, 11, 15)


def test_add_treatment_counts_the_one_it_just_added(db, fixtures):
    """Visit.items is lazy="selectin", so session.get loads it eagerly and a
    VisitItem inserted by visit_id leaves the loaded collection stale. Summing
    that stale collection silently drops the new treatment's minutes."""
    with db.session() as s:
        visit = visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                            [fixtures["ped"]], created_by="1")
        visits.add_treatment(s, visit.id, fixtures["gel"])
    with db.session() as s:
        from app.models import Visit
        reloaded = s.get(Visit, 1)
        assert len(reloaded.items) == 2
        assert sum(i.unit_price_cents for i in reloaded.items) == 4300


def test_overlapping_booking_is_refused(db, fixtures):
    with db.session() as s:
        visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                    [fixtures["ped"]], created_by="1")
    with db.session() as s:
        with pytest.raises(visits.SlotTaken):
            visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10, 30),
                        [fixtures["gel"]], created_by="1")


def test_touching_visits_do_not_overlap(db, fixtures):
    """10:00-10:45 and 10:45-11:15 share an instant and must both stand, or
    every back to back booking is refused."""
    with db.session() as s:
        visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                    [fixtures["ped"]], created_by="1")
    with db.session() as s:
        visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10, 45),
                    [fixtures["gel"]], created_by="1")


def test_a_cancelled_visit_frees_its_slot(db, fixtures):
    with db.session() as s:
        first = visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                            [fixtures["ped"]], created_by="1")
        visits.set_status(s, first.id, "cancelled")
    with db.session() as s:
        visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                    [fixtures["gel"]], created_by="1")   # must not raise


def test_booking_an_unknown_client_is_refused_before_the_insert(db, fixtures):
    with db.session() as s:
        with pytest.raises(LookupError):
            visits.book(s, 999, _local(2026, 9, 10, 10),
                        [fixtures["ped"]], created_by="1")


def test_a_visit_needs_at_least_one_treatment(db, fixtures):
    with db.session() as s:
        with pytest.raises(ValueError):
            visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                        [], created_by="1")


def test_reschedule_may_keep_its_own_slot(db, fixtures):
    with db.session() as s:
        visit = visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                            [fixtures["ped"]], created_by="1")
        visits.reschedule(s, visit.id, _local(2026, 9, 10, 10, 15),
                          _local(2026, 9, 10, 11))
        assert timeutil.from_utc_iso(visit.starts_at) == _local(2026, 9, 10, 10, 15)


def test_unclosed_lists_only_past_planned_visits(db, fixtures):
    with db.session() as s:
        past = visits.book(s, fixtures["client_id"], _local(2020, 1, 6, 10),
                           [fixtures["ped"]], created_by="1")
        done = visits.book(s, fixtures["client_id"], _local(2020, 1, 6, 12),
                           [fixtures["gel"]], created_by="1")
        visits.set_status(s, done.id, "done")
        visits.book(s, fixtures["client_id"], _local(2099, 1, 6, 10),
                    [fixtures["ped"]], created_by="1")
    with db.session() as s:
        assert [v.id for v in visits.unclosed(s)] == [past.id]


def test_two_parallel_bookings_cannot_take_the_same_slot(db, fixtures):
    """Measured before the fix: four threads, four visits committed, the day
    double booked. pysqlite opens a transaction lazily and only just before a
    write, so every check-then-write is a race until the connection begins
    IMMEDIATE."""
    import threading

    from app.models import Visit

    start = _local(2026, 9, 10, 10)
    go = threading.Event()
    outcomes = []

    def attempt():
        go.wait()
        try:
            with db.session() as s:
                visits.book(s, fixtures["client_id"], start,
                            [fixtures["ped"]], created_by="1")
            outcomes.append("booked")
        except visits.SlotTaken:
            outcomes.append("taken")

    threads = [threading.Thread(target=attempt) for _ in range(4)]
    for t in threads:
        t.start()
    go.set()
    for t in threads:
        t.join()

    assert outcomes.count("booked") == 1
    assert outcomes.count("taken") == 3
    with db.session() as s:
        assert s.query(Visit).count() == 1


def test_growth_stops_at_the_next_client_instead_of_swallowing_them(db, fixtures):
    """Closing flow: 10:00-10:45, next client 11:00. Adding a 30 minute
    treatment wants 11:15, which would silently overlap. The work is recorded
    either way; the block stops at 11:00."""
    with db.session() as s:
        first = visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                            [fixtures["ped"]], created_by="1")
        visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 11),
                    [fixtures["gel"]], created_by="1")
    with db.session() as s:
        visits.add_treatment(s, first.id, fixtures["gel"])
    with db.session() as s:
        from app.models import Visit
        visit = s.get(Visit, first.id)
        assert timeutil.from_utc_iso(visit.ends_at) == _local(2026, 9, 10, 11)
        assert len(visit.items) == 2         # the money is still right
        assert visits.overlapping(s, visit.starts_at, visit.ends_at,
                                  exclude_id=visit.id) == []


def test_a_cancelled_visit_cannot_be_revived_into_a_taken_slot(db, fixtures):
    with db.session() as s:
        first = visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                            [fixtures["ped"]], created_by="1")
        visits.set_status(s, first.id, "cancelled")
        visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                    [fixtures["gel"]], created_by="1")
    with db.session() as s:
        with pytest.raises(visits.SlotTaken):
            visits.set_status(s, first.id, "planned")


def test_reschedule_refuses_another_visits_window(db, fixtures):
    with db.session() as s:
        first = visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                            [fixtures["ped"]], created_by="1")
        visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 14),
                    [fixtures["gel"]], created_by="1")
    with db.session() as s:
        with pytest.raises(visits.SlotTaken):
            visits.reschedule(s, first.id, _local(2026, 9, 10, 14, 15),
                              _local(2026, 9, 10, 15))


def test_an_archived_client_cannot_be_booked(db, fixtures):
    with db.session() as s:
        clients.archive(s, fixtures["client_id"])
    with db.session() as s:
        with pytest.raises(visits.UnknownClient):
            visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                        [fixtures["ped"]], created_by="1")


def test_an_unknown_treatment_is_its_own_error(db, fixtures):
    with db.session() as s:
        with pytest.raises(visits.UnknownTreatment):
            visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                        [999], created_by="1")


# ---- the DST Sundays the spec asks for ----

def test_a_window_spanning_the_autumn_fall_back_is_the_minutes_asked_for(db, fixtures):
    """2026-10-25: 02:00 local happens twice. Wall clock addition would store
    a 60 minute Visit as a 120 minute block and lose an hour of the day."""
    with db.session() as s:
        visit = visits.book(s, fixtures["client_id"], _local(2026, 10, 25, 2, 30),
                            [fixtures["gel"]], created_by="1")   # 30 minutes
        assert _elapsed_minutes(visit) == 30


def test_a_window_spanning_the_spring_forward_is_the_minutes_asked_for(db, fixtures):
    """2027-03-28: 02:00 to 03:00 local does not exist."""
    with db.session() as s:
        visit = visits.book(s, fixtures["client_id"], _local(2027, 3, 28, 1, 45),
                            [fixtures["gel"]], created_by="1")
        assert _elapsed_minutes(visit) == 30
        # 01:45 CET plus 30 minutes is 03:15 CEST: 02:00 never happened
        end = timeutil.from_utc_iso(visit.ends_at)
        assert (end.hour, end.minute) == (3, 15)


def test_a_time_the_spring_forward_skipped_is_refused(db, fixtures):
    with db.session() as s:
        with pytest.raises(timeutil.NonExistentTime):
            visits.book(s, fixtures["client_id"], _local(2027, 3, 28, 2, 30),
                        [fixtures["ped"]], created_by="1")


@pytest.mark.parametrize("moment", [
    _local(2026, 10, 25, 1, 30),    # before the autumn fall back
    _local(2026, 10, 25, 3, 30),    # after it
    _local(2027, 3, 28, 1, 30),     # before the spring forward
    _local(2027, 3, 28, 3, 30),     # after it
    _local(2026, 7, 1, 12),
    _local(2026, 1, 1, 12),
])
def test_utc_round_trip_is_the_identity(moment):
    assert timeutil.from_utc_iso(timeutil.to_utc_iso(moment)) == moment


def test_the_stored_shape_is_enforced_not_just_agreed(db, fixtures):
    """One "+00:00" row sorts below every "Z" row and disappears from the
    overlap check, so the shape is a constraint, not a convention."""
    import sqlite3

    with db.session() as s:
        visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                    [fixtures["ped"]], created_by="1")
    con = sqlite3.connect(db.engine.url.database)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO visit (client_id, starts_at, ends_at, created_by,"
            " created_at) VALUES (1, '2026-09-11T08:00:00+00:00',"
            " '2026-09-11T09:00:00+00:00', '1', '2026-09-10T08:00:00Z')")
    con.close()


def test_comparing_two_local_datetimes_is_wall_clock_not_elapsed(db, fixtures):
    """The trap that bit the end-after-start guard: same tzinfo means Python
    ignores the offset. This is why the service works in UTC."""
    autumn_start = _local(2026, 10, 25, 2, 30)          # CEST, 00:30Z
    with db.session() as s:
        visit = visits.book(s, fixtures["client_id"], autumn_start,
                            [fixtures["gel"]], created_by="1")
    end_local = timeutil.from_utc_iso(visit.ends_at)
    assert end_local < autumn_start                     # wall clock says earlier
    assert (timeutil.to_utc(end_local)
            > timeutil.to_utc(autumn_start))            # real time says later
