"""
Database models for MVP backend using SQLAlchemy ORM.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class POI(Base):
    """POI (Points of Interest) table."""

    __tablename__ = "pois"

    poi_id: str = Column(String(50), primary_key=True, nullable=False)
    name: str = Column(String(255), nullable=False, index=True)
    type: str = Column(String(50), index=True)
    address: str = Column(String(500))
    location: str = Column(String(255))
    longitude: float = Column(Float, nullable=False)
    latitude: float = Column(Float, nullable=False)
    rating: Optional[float] = Column(Float, nullable=True)
    cost: Optional[float] = Column(Float, nullable=True)
    source_keyword: str = Column(String(100), nullable=False, index=True)
    source_provider: Optional[str] = Column(String(50), nullable=True, index=True)
    source_id: Optional[str] = Column(String(100), nullable=True, index=True)
    source_key: Optional[str] = Column(String(100), nullable=True, index=True)
    category_major: Optional[str] = Column(String(100), nullable=True, index=True)
    category_minor: Optional[str] = Column(String(100), nullable=True)
    source_type: Optional[str] = Column(String(255), nullable=True)
    source_typecode: Optional[str] = Column(String(50), nullable=True)
    phone: Optional[str] = Column(String(100), nullable=True)
    business_time: Optional[str] = Column(String(100), nullable=True)
    raw_tags: Optional[str] = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    deals = relationship("Deal", back_populates="poi", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<POI {self.poi_id}: {self.name}>"


class Deal(Base):
    """Deal (团购) table."""

    __tablename__ = "deals"

    deal_id: str = Column(String(50), primary_key=True, nullable=False)
    poi_id: str = Column(String(50), ForeignKey("pois.poi_id"), nullable=False, index=True)
    name: str = Column(String(255), nullable=False)
    category: str = Column(String(100), nullable=False, index=True)
    deal_title: str = Column(String(500), nullable=False)
    price: float = Column(Float, nullable=False)
    original_price: Optional[float] = Column(Float, nullable=True)
    # Store as JSON string in SQLite
    included_items: str = Column(Text, nullable=True)
    additional_information: str = Column(String(500), nullable=True)
    valid_time: str = Column(String(100), nullable=True)
    rating: Optional[float] = Column(Float, nullable=True)
    monthly_sales: Optional[int] = Column(Integer, nullable=True)
    # Store as JSON string in SQLite
    reviews: str = Column(Text, nullable=True)
    business_time: str = Column(String(100), nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    poi = relationship("POI", back_populates="deals")

    def __repr__(self) -> str:
        return f"<Deal {self.deal_id}: {self.deal_title}>"
