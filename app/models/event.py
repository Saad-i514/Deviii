
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class CheckIn(Base):
    __tablename__ = "checkins"
    
    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(Integer, ForeignKey("participants.id"))
    event_type = Column(String)  
    checked_in_at = Column(DateTime(timezone=True), server_default=func.now())
    checked_by = Column(Integer, ForeignKey("users.id"))
    
   
    participant = relationship("Participant", back_populates="check_ins")

 