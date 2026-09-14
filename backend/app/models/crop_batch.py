import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base

class CropBatch(Base):
    __tablename__ = "crop_batches"

    batch_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    zone_id = Column(String(36), ForeignKey("zones.zone_id", ondelete="CASCADE"), nullable=False)
    farmer_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    fruit_type = Column(String(50), nullable=False) # 'Orange', 'Banana', 'Tomato', 'Pineapple'
    quantity_kg = Column(Float, nullable=False)
    intake_date = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    expected_shelf_life_days = Column(Integer, default=30)
    current_health_status = Column(String(20), default="Good") # 'Good', 'Degrading', 'Bad'

    # Relationships
    zone = relationship("Zone", back_populates="batches")
    farmer = relationship("User")

    def __repr__(self):
        return f"<CropBatch(fruit='{self.fruit_type}', qty={self.quantity_kg}kg, health='{self.current_health_status}')>"

