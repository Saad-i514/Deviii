from sqlalchemy import Column, Integer, String,  DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Team(Base):
    __tablename__ = "teams"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    code = Column(String, unique=True, nullable=False)
    track = Column(String, nullable=False)   
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
     
    members = relationship("Participant", back_populates="team")
    payments = relationship("Payment", back_populates="team")