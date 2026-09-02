import datetime
import uuid
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (
        Index("ix_snapshots_wallet_date", "wallet_address", "snapshot_date"),
        Index("ix_snapshots_date", "snapshot_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wallet_address: Mapped[str] = mapped_column(
        String(42), ForeignKey("wallets.address", ondelete="CASCADE"), unique=True, index=True
    )

    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    total_volume_usdc: Mapped[float] = mapped_column(Float, default=0.0)
    total_pnl_usdc: Mapped[float] = mapped_column(Float, default=0.0)
    total_trades_count: Mapped[int] = mapped_column(Integer, default=0)
    active_positions_count: Mapped[int] = mapped_column(Integer, default=0)
    snapshot_date: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now()
    )


    wallet = relationship("Wallet", back_populates="snapshots")

