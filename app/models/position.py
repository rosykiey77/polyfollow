import datetime
import uuid
from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wallet_address: Mapped[str] = mapped_column(
        String(42), ForeignKey("wallets.address", ondelete="CASCADE"), index=True
    )
    condition_id: Mapped[str] = mapped_column(String(255), index=True)
    asset_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    market_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    outcome: Mapped[str] = mapped_column(String(50), default="YES")
    size: Mapped[float] = mapped_column(Float, default=0.0)
    avg_price: Mapped[float] = mapped_column(Float, default=0.0)
    current_price: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    cur_value: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    wallet = relationship("Wallet", back_populates="positions")
