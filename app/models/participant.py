from sqlalchemy import Column, Integer, String, Boolean, Enum,  ForeignKey, Text
from sqlalchemy.orm import relationship
 
import enum
from app.database import Base

class Track(str, enum.Enum):
    PROGRAMMING = "programming"
    IDEATHON = "ideathon"
    COMPETITIVE_PROGRAMMING = "competitive_programming"
    GAMING = "gaming"
    SOCIALITE = "socialite"

class TShirtSize(str, enum.Enum):
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"
    XXL = "XXL"

class Participant(Base):
    __tablename__ = "participants"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    student_id = Column(String, unique=True, nullable=False)
    cnic = Column(String, unique=True, nullable=False)
    track = Column(Enum(Track), nullable=False)
    technical_skills = Column(Text)
    github_link = Column(String)
    portfolio_link = Column(String)
    tshirt_size = Column(Enum(TShirtSize), nullable=False)
    dietary_requirements = Column(Text)
    emergency_contact = Column(String)
    
     
    is_team_lead = Column(Boolean, default=False)
    team_id = Column(Integer, ForeignKey("teams.id"))
    registration_complete = Column(Boolean, default=False)
    
   
    user = relationship("User", back_populates="participant")
    team = relationship("Team", back_populates="members")
    payment = relationship("Payment", back_populates="participant", uselist=False)
    check_ins = relationship("CheckIn", back_populates="participant")