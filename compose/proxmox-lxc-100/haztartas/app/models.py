"""The tables. The schema of record is app/migrations/*.sql; these classes
mirror it and must be changed together with a new migration.
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    username: Mapped[str] = mapped_column(String, unique=True)
    role: Mapped[str] = mapped_column(String)   # 'adult' | 'child'
    password_hash: Mapped[str] = mapped_column(String)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[str | None] = mapped_column(String, nullable=True)


class Wallet(Base):
    __tablename__ = "wallet"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    # NULL = the household wallet
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id"), unique=True, nullable=True)


class Category(Base):
    __tablename__ = "category"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)   # 'expense' | 'income'
    monthly_limit_eur_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    archived_at: Mapped[str | None] = mapped_column(String, nullable=True)


class Recurring(Base):
    __tablename__ = "recurring"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"))
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String)
    day_of_month: Mapped[int] = mapped_column(Integer)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True)
    archived_at: Mapped[str | None] = mapped_column(String, nullable=True)


class Entry(Base):
    __tablename__ = "entry"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_uuid: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallet.id"))
    kind: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)   # 'draft' | 'confirmed'
    date: Mapped[str] = mapped_column(String)     # local YYYY-MM-DD
    merchant: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String)
    eur_minor: Mapped[int] = mapped_column(Integer)
    fx_rate: Mapped[str] = mapped_column(String)   # Decimal as text
    category_id: Mapped[int | None] = mapped_column(ForeignKey("category.id"), nullable=True)
    payment: Mapped[str] = mapped_column(String)   # 'cash' | 'card' | 'other'
    hidden: Mapped[int] = mapped_column(Integer, default=0)
    reveal_on: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str | None] = mapped_column(String, nullable=True)
    deleted_at: Mapped[str | None] = mapped_column(String, nullable=True)
    transfer_group: Mapped[str | None] = mapped_column(String, nullable=True)
    recurring_id: Mapped[int | None] = mapped_column(ForeignKey("recurring.id"), nullable=True)
    recurring_month: Mapped[str | None] = mapped_column(String, nullable=True)


class FxRate(Base):
    __tablename__ = "fx_rate"
    date: Mapped[str] = mapped_column(String, primary_key=True)
    currency: Mapped[str] = mapped_column(String, primary_key=True)
    rate: Mapped[str] = mapped_column(String)
