from pydantic import BaseModel 
from typing import Optional 
from datetime import datetime
from enum import Enum

class Track(str, Enum):
    PROGRAMMING = "programming"
    IDEATHON = "ideathon"
    COMPETITIVE_PROGRAMMING = "competitive_programming"
    GAMING = "gaming"
    SOCIALITE = "socialite"

class TShirtSize(str, Enum):
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"
    XXL = "XXL"

class ParticipantBase(BaseModel):
    student_id: str
    cnic: str
    track: Track
    technical_skills: Optional[str] = None
    github_link: Optional[str] = None
    portfolio_link: Optional[str] = None
    tshirt_size: Optional[TShirtSize] = None

    dietary_requirements: Optional[str] = None
    emergency_contact: str

class ParticipantCreate(ParticipantBase):
    team_code: Optional[str] = None
    create_new_team: bool = False
    team_name: Optional[str] = None

class ParticipantUpdate(BaseModel):
    technical_skills: Optional[str] = None
    github_link: Optional[str] = None
    portfolio_link: Optional[str] = None
    dietary_requirements: Optional[str] = None
    emergency_contact: Optional[str] = None

class ParticipantInDB(ParticipantBase):
    id: int
    user_id: int
    is_team_lead: bool
    team_id: Optional[int]
    registration_complete: bool
    created_at: datetime
    
    class Config:
        from_attributes = True