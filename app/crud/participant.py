from sqlalchemy.orm import Session
from app.models.participant import Participant
from app.schemas.participant import ParticipantCreate
import random
import string

def generate_team_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def create_participant(db: Session, participant: ParticipantCreate, user_id: int):
    db_participant = Participant(
        user_id=user_id,
        student_id=participant.student_id,
        cnic=participant.cnic,
        track=participant.track,
        technical_skills=participant.technical_skills,
        github_link=participant.github_link,
        portfolio_link=participant.portfolio_link,
        tshirt_size=participant.tshirt_size,
        dietary_requirements=participant.dietary_requirements,
        emergency_contact=participant.emergency_contact
    )
    db.add(db_participant)
    db.commit()
    db.refresh(db_participant)
    return db_participant

def get_participant_by_user_id(db: Session, user_id: int):
    return db.query(Participant).filter(Participant.user_id == user_id).first()

def get_participants_by_track(db: Session, track: str):
    return db.query(Participant).filter(Participant.track == track).all()