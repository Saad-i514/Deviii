from sqlalchemy import Column, Integer, String, Float, Boolean, Enum, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base

class PaymentMethod(str, enum.Enum):
    ONLINE = "online"
    CASH = "cash"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    PENDING_CASH = "pending_cash"

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(Integer, ForeignKey("participants.id"), unique=True)
    team_id = Column(Integer, ForeignKey("teams.id"))
    amount = Column(Float, nullable=False)
    payment_method = Column(Enum(PaymentMethod), nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    
    # Online payment details
    transaction_id = Column(String)
    receipt_path = Column(String)
    uploaded_at = Column(DateTime(timezone=True))
    
    # Cash payment details
    verified_by = Column(Integer, ForeignKey("users.id"))
    verified_at = Column(DateTime(timezone=True))
    
    # Relationships
    participant = relationship("Participant", back_populates="payment")
    team = relationship("Team", back_populates="payments")
    
    # Audit trail
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())