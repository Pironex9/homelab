"""Phase 1 tables. The schema of record is app/migrations/001_schema.sql;
these classes mirror it and must be changed together with a new migration.
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    username: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    is_admin: Mapped[int] = mapped_column(Integer, default=0)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[str | None] = mapped_column(String, nullable=True)


class Client(Base):
    __tablename__ = "client"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    alert: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    interval_override_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    archived_at: Mapped[str | None] = mapped_column(String, nullable=True)
    erased_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)


class Treatment(Base):
    __tablename__ = "treatment"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    duration_min: Mapped[int] = mapped_column(Integer)
    price_cents: Mapped[int] = mapped_column(Integer)
    active: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(String)


class Visit(Base):
    __tablename__ = "visit"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"))
    starts_at: Mapped[str] = mapped_column(String)
    ends_at: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="planned")
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[str | None] = mapped_column(String, nullable=True)
    closed_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)

    client: Mapped[Client] = relationship(lazy="joined")
    items: Mapped[list["VisitItem"]] = relationship(
        back_populates="visit", lazy="selectin")


class VisitItem(Base):
    __tablename__ = "visit_item"
    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visit.id"))
    kind: Mapped[str] = mapped_column(String)
    treatment_id: Mapped[int | None] = mapped_column(
        ForeignKey("treatment.id"), nullable=True)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qty: Mapped[float] = mapped_column(Float, default=1)
    unit_price_cents: Mapped[int] = mapped_column(Integer)

    visit: Mapped[Visit] = relationship(back_populates="items")
    treatment: Mapped[Treatment | None] = relationship(lazy="joined")


class WorkingHours(Base):
    __tablename__ = "working_hours"
    id: Mapped[int] = mapped_column(primary_key=True)
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date: Mapped[str | None] = mapped_column(String, nullable=True)
    start: Mapped[str] = mapped_column(String)
    end: Mapped[str] = mapped_column(String)
    is_closed: Mapped[int] = mapped_column(Integer, default=0)


class Setting(Base):
    __tablename__ = "setting"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)
