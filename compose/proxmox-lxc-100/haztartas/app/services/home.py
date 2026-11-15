"""The home screen's view model: what templates/home.html reads."""
from __future__ import annotations

from sqlalchemy import func, or_, select

from app.models import Category, Entry, Wallet
from app.services import summary, visibility
from app.services.treemap import squarify
from app.strings.hu import MONTHS, MONTHS_IN, S, day_label


def hue(category_id: int | None) -> str:
    return "c-other" if category_id is None else f"c{category_id % 8}"


def shift_month(month: str, delta: int) -> str:
    n = int(month[:4]) * 12 + int(month[5:7]) - 1 + delta
    return f"{n // 12:04d}-{n % 12 + 1:02d}"


def date_label(day: str) -> str:
    """"2026-11-14" -> "november 14." """
    return f"{MONTHS[int(day[5:7]) - 1]} {int(day[8:10])}."


def _tiles(rows, month: str, names: dict, limits: dict, hidden: dict) -> list[dict]:
    """rows: [(category_id, eur_minor)]; layout, fold and decorate."""
    rects = squarify([(cid, v) for cid, v in rows])
    amounts = dict(rows)
    shown = {r.key for r in rects}
    folded = [cid for cid, v in rows if cid not in shown and v > 0]
    total = sum(v for _, v in rows if v > 0)
    tiles = []
    for i, r in enumerate(rects):
        if r.key == "other":
            amount = sum(amounts[cid] for cid in folded)
            t = dict(name=S["other_tile"].format(n=len(folded)), note=None,
                     hue="c-other", limit_minor=None, used_pct=0, over=False,
                     url=f"/entries?month={month}")
        else:
            amount = amounts[r.key]
            limit = limits.get(r.key)
            n = hidden.get(r.key, 0)
            t = dict(name=names[r.key], hue=hue(r.key), limit_minor=limit,
                     note=S["hidden_count"].format(n=n) if n else None,
                     used_pct=min(100, round(amount * 100 / limit)) if limit else 0,
                     over=bool(limit) and amount > limit,
                     url=f"/entries?month={month}&category={r.key}")
        share = amount / total
        t.update(amount_minor=amount, x=round(r.x, 4), y=round(r.y, 4),
                 w=round(r.w, 4), h=round(r.h, 4),
                 size="big" if i == 0 and share >= 0.3
                 else "small" if share < 0.1 else "")
        tiles.append(t)
    return tiles


def build(s, viewer, month: str, today: str) -> dict:
    year, mon = int(month[:4]), int(month[5:7])
    current = today[:7]
    ctx = dict(
        view=viewer.role, month_label=f"{year}. {MONTHS[mon - 1]}",
        month_in=MONTHS_IN[mon - 1], prev_url=f"/?month={shift_month(month, -1)}",
        next_url=(f"/?month={shift_month(month, 1)}" if month < current else None),
        balance_minor=0, expected=[], drafts_count=0, pending=0, tiles=[],
        by_author=[], wallet_balance_minor=0, own_entries=[])

    if viewer.role == "adult":
        sm = summary.month_summary(s, month, today)
        secret = dict(s.execute(
            select(Entry.category_id, func.count())
            .where(Entry.wallet_id == summary._household_id(s),
                   Entry.status == "confirmed", Entry.deleted_at.is_(None),
                   Entry.date.like(f"{month}-%"), Entry.kind == "expense",
                   Entry.hidden != 0,
                   or_(Entry.reveal_on.is_(None), Entry.reveal_on > today))
            .group_by(Entry.category_id)).all())
        # A past month would list its salaries as still expected.
        expected = sm.expected if month == current else []
        ctx.update(
            balance_minor=sm.balance_eur_minor, by_author=sm.by_author,
            expected=[dict(name=e.name, day_label=day_label(int(e.day[8:])))
                      for e in expected],
            drafts_count=s.scalar(select(func.count()).select_from(Entry).where(
                Entry.status == "draft", Entry.deleted_at.is_(None),
                Entry.wallet_id == summary._household_id(s))),
            tiles=_tiles(
                [(c.category_id, c.spent_eur_minor) for c in sm.categories],
                month, {c.category_id: c.name for c in sm.categories},
                {c.category_id: c.limit_eur_minor for c in sm.categories},
                secret))
        return ctx

    wallet = s.scalars(select(Wallet).where(
        Wallet.owner_user_id == viewer.id)).one_or_none()
    if wallet is None:
        return ctx
    own = (Entry.wallet_id == wallet.id, Entry.status == "confirmed",
           visibility.listable(viewer, today))
    spent = s.execute(
        select(Entry.category_id, Category.name, func.sum(Entry.eur_minor))
        .join(Category, Category.id == Entry.category_id)
        .where(*own, Entry.kind == "expense", Entry.date.like(f"{month}-%"))
        .group_by(Entry.category_id, Category.name)
        .order_by(func.sum(Entry.eur_minor).desc())).all()
    recent = s.execute(
        select(Entry, Category.name)
        .outerjoin(Category, Category.id == Entry.category_id)
        # Everything the child may see: what they authored in either wallet
        # plus what landed in their own (exactly visibility.listable).
        .where(Entry.status == "confirmed", visibility.listable(viewer, today))
        .order_by(Entry.date.desc(), Entry.id.desc()).limit(20)).all()
    ctx.update(
        wallet_balance_minor=summary.wallet_balance(s, wallet.id, viewer, today),
        tiles=_tiles([(cid, int(v)) for cid, _, v in spent], month,
                     {cid: n for cid, n, _ in spent}, {}, {}),
        own_entries=[dict(
            what=e.merchant or e.note or cname or S["no_name"],
            meta=f"{cname or ''} · {date_label(e.date)}".strip(" ·"),
            kind=e.kind, amount_minor=e.eur_minor, hue=hue(e.category_id))
            for e, cname in recent])
    return ctx
