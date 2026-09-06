"""One row per model against the real migration.

models.py mirrors 001_schema.sql by hand and nothing keeps them in step:
Base.metadata never creates anything. A misspelled column would otherwise ship
and surface as a 500 on whichever screen touches it first.
"""
import pytest

from app import migrate
from app.db import Database
from app.models import (Client, Setting, Treatment, User, Visit, VisitItem,
                        WorkingHours)


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


def test_every_model_round_trips(db):
    with db.session() as s:
        s.add(User(name="A", username="a", password_hash="x"))
        s.add(Client(name="Kliens", phone="+421900000000", alert="cukorbeteg",
                     created_by="test", created_at="2026-09-06T10:00:00Z"))
        s.add(Treatment(name="Pedikur", duration_min=60, price_cents=2500,
                        created_by="test"))
        s.flush()
        s.add(Visit(client_id=1, starts_at="2026-09-07T07:00:00Z",
                    ends_at="2026-09-07T08:00:00Z", created_by="test",
                    created_at="2026-09-06T10:00:00Z"))
        s.flush()
        s.add(VisitItem(visit_id=1, kind="treatment", treatment_id=1,
                        qty=1, unit_price_cents=2500))
        s.add(WorkingHours(date="2026-12-24", start="00:00", end="00:00",
                           is_closed=1))
        s.add(Setting(key="test_key", value="test_value"))

    with db.session() as s:
        visit = s.get(Visit, 1)
        assert visit.client.name == "Kliens"
        assert visit.items[0].treatment.name == "Pedikur"
        assert visit.status == "planned"
        assert s.get(Setting, "test_key").value == "test_value"
        assert s.query(WorkingHours).filter_by(is_closed=1).one().end == "00:00"
