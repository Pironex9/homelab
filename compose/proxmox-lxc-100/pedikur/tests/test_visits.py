from datetime import datetime

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
