"""How many Treatments one unit of a Product lasts for.

The question is asked this way round on purpose: nobody knows they use 0.4 ml
of lacquer, and everybody knows a bottle gives about thirty fills. Consumption
is then 1/treatments_per_unit, which is where the fractional stock figure
comes from.

Recipes are configuration, not history, so remove() is a real delete. Nothing
is lost by it: consumption is already posted as Stock Movements, and those are
append-only and untouched by anything in this module.

Only the expensive materials get a recipe (lacquer, gel, abrasive caps), by
decision on 2026-09-12. A Treatment with no recipe posts no consumption, and
that is not a bug. The consequence travels to the dashboard: the margin figure
counts only what carries a recipe, and must never be labelled as though it
covered everything.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TreatmentRecipe


def for_treatment(session: Session, treatment_id: int) -> list[TreatmentRecipe]:
    return list(session.scalars(
        select(TreatmentRecipe)
        .where(TreatmentRecipe.treatment_id == treatment_id)
        .order_by(TreatmentRecipe.id)))


def by_treatment(session: Session) -> dict[int, list[TreatmentRecipe]]:
    """Every recipe, grouped, in one query. The treatment list screen needs
    all of them at once and the reconcile needs one treatment's worth; this is
    the shape that keeps the list screen off an N+1."""
    grouped: dict[int, list[TreatmentRecipe]] = defaultdict(list)
    for row in session.scalars(
            select(TreatmentRecipe).order_by(TreatmentRecipe.id)):
        grouped[row.treatment_id].append(row)
    return dict(grouped)


def set_for(session: Session, treatment_id: int, product_id: int,
            treatments_per_unit: float) -> TreatmentRecipe:
    """Upsert on the (treatment, product) pair.

    Upsert rather than insert because the UNIQUE index would otherwise raise
    an IntegrityError at commit, long after the route left its try block, and
    correcting a yield she guessed badly is the normal case rather than the
    exceptional one.
    """
    yield_per_unit = float(treatments_per_unit)
    if yield_per_unit <= 0:
        # Also a CHECK constraint. Repeated here because consumption is
        # 1/this: a zero reaching the close path is a ZeroDivisionError with a
        # client in the chair.
        raise ValueError(
            "one unit has to last for at least a fraction of a treatment")
    row = session.scalars(
        select(TreatmentRecipe)
        .where(TreatmentRecipe.treatment_id == treatment_id,
               TreatmentRecipe.product_id == product_id)).one_or_none()
    if row is None:
        row = TreatmentRecipe(treatment_id=treatment_id, product_id=product_id,
                              treatments_per_unit=yield_per_unit)
        session.add(row)
    else:
        row.treatments_per_unit = yield_per_unit
    session.flush()
    return row


def remove(session: Session, recipe_id: int) -> None:
    row = session.get(TreatmentRecipe, recipe_id)
    if row is None:
        raise LookupError(f"no recipe {recipe_id}")
    session.delete(row)
    session.flush()
