import datetime
import uuid
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        Index("ix_trades_condition_traded_at", "condition_id", "traded_at"),
        Index("ix_trades_wallet_traded_at", "wallet_address", "traded_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wallet_address: Mapped[str] = mapped_column(
        String(42), ForeignKey("wallets.address", ondelete="CASCADE"), index=True
    )
    transaction_hash: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    condition_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    asset_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    market_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    side: Mapped[str] = mapped_column(String(20), default="BUY")  # BUY or SELL
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)  # YES or NO
    size: Mapped[float] = mapped_column(Float, default=0.0)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    usdc_size: Mapped[float] = mapped_column(Float, default=0.0)
    traded_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True)
    is_read_by_agent: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now()
    )

    wallet = relationship("Wallet", back_populates="trades")

