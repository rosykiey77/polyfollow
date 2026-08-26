import datetime
from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


class Wallet(Base):
    __tablename__ = "wallets"

    address: Mapped[str] = mapped_column(String(42), primary_key=True, index=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    positions = relationship("Position", back_populates="wallet", cascade="all, delete-orphan", lazy="selectin")
    trades = relationship("Trade", back_populates="wallet", cascade="all, delete-orphan", lazy="selectin")
    snapshots = relationship("Snapshot", back_populates="wallet", cascade="all, delete-orphan", lazy="selectin")
