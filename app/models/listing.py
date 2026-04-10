from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    seller_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    card_id: Mapped[int] = mapped_column(Integer, ForeignKey("cards.id"), nullable=False)

    grading_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("gradings.id"), nullable=True)

    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    condition: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    ) 

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    image_urls: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )

    is_negotiable: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    seller = relationship("User", back_populates="listings")
    card = relationship("Card", back_populates="listings")
    grading = relationship("Grading", back_populates="listing")
    orders = relationship("Order", back_populates="listing", lazy="select")

    @property
    def first_image(self):
        if not self.image_urls:
            return None
        return self.image_urls.split(",")[0].strip()

    @property
    def is_graded(self):
        return self.grading_id is not None

    def __repr__(self):
        return f"<Listing #{self.id} Rp{self.price}>"