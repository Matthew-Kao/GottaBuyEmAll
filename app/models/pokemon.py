from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Pokemon(Base):
    __tablename__ = "pokemon"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pokedex_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    primary_type: Mapped[str] = mapped_column(String(50), nullable=False)
    secondary_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    fun_fact: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    cards = relationship("Card", back_populates="pokemon", lazy="select")

    def __repr__(self):
        return f"<Pokemon #{self.pokedex_number} {self.name}>"