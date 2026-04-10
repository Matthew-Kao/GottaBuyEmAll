from datetime import datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pokemon_id: Mapped[int] = mapped_column(Integer, ForeignKey("pokemon.id"), nullable=False)

    set_name: Mapped[str] = mapped_column(String(100), nullable=False)
    set_code: Mapped[str | None] = mapped_column(String(20), nullable=True)   
    card_number: Mapped[str | None] = mapped_column(String(20), nullable=True) 

    rarity: Mapped[str] = mapped_column(
        String(50), nullable=False
    ) 

    card_variant: Mapped[str] = mapped_column(
        String(50), nullable=False, default="normal"
    )  

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    pokemon = relationship("Pokemon", back_populates="cards")
    listings = relationship("Listing", back_populates="card", lazy="select")

    def __repr__(self):
        return f"<Card {self.set_name} - {self.card_number}>"


class Grading(Base):
    __tablename__ = "gradings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    grading_service: Mapped[str] = mapped_column(String(20), nullable=False)
    grade: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)

    cert_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    graded_at: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    listing = relationship("Listing", back_populates="grading", uselist=False)

    def __repr__(self):
        return f"<Grading {self.grading_service} {self.grade} cert#{self.cert_number}>"