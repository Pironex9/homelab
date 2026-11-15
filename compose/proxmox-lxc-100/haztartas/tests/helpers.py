"""Seeding for route tests: real services, real database."""
from sqlalchemy import select

from app import clock
from app.models import Category, User, Wallet
from app.services.entries import EntryInput, create_entry


def user(app, username):
    with app.state.db.session() as s:
        return s.scalars(select(User).where(User.username == username)).one()


def household(app):
    with app.state.db.session() as s:
        return s.scalars(select(Wallet).where(
            Wallet.owner_user_id.is_(None))).one().id


def child_wallet(app):
    cili = user(app, "cili")
    with app.state.db.session() as s:
        w = s.scalars(select(Wallet).where(
            Wallet.owner_user_id == cili.id)).one_or_none()
        if w is None:
            w = Wallet(name="Cili", owner_user_id=cili.id)
            s.add(w)
            s.flush()
        return w.id


def cat(app, name, kind="expense"):
    with app.state.db.session() as s:
        return s.scalars(select(Category).where(
            Category.name == name, Category.kind == kind)).one().id


def add(app, username, wallet_id=None, **kw):
    """One confirmed entry by `username`; defaults to a 10 EUR Lidl card spend
    today in the household wallet."""
    base = dict(wallet_id=wallet_id or household(app), kind="expense",
                date=clock.today(), amount_minor=1000, currency="EUR",
                category_id=cat(app, "Élelmiszer"), merchant="Lidl",
                note=None, payment="card", hidden=False, reveal_on=None)
    base.update(kw)
    status = base.pop("status", "confirmed")
    with app.state.db.session() as s:
        author = s.scalars(select(User).where(User.username == username)).one()
        return create_entry(s, author, EntryInput(**base), status=status).id


def form(app, **kw):
    """A valid POST /entries body."""
    base = dict(kind="expense", amount="12,50", currency="EUR",
                date=clock.today(), merchant="Tesco", note="", payment="card",
                wallet_id=str(household(app)),
                category_id=str(cat(app, "Élelmiszer")))
    base.update(kw)
    return base
