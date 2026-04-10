from datetime import datetime
 
from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
 
from app.database import Base
 
 
class User(Base):
    __tablename__ = "users"
 
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
 
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
 
    # seller stats — updated whenever an order completes
    seller_rating: Mapped[float] = mapped_column(Float, default=0.0)
    total_sales: Mapped[int] = mapped_column(Integer, default=0)
 
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
 
    # relationships
    listings = relationship("Listing", back_populates="seller", lazy="select")
    orders_as_buyer = relationship("Order", back_populates="buyer", foreign_keys="Order.buyer_id", lazy="select")
 
    def __repr__(self):
        return f"<User {self.username}>"
 