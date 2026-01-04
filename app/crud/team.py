from sqlalchemy.orm import Session
from app.models.team import Team
from app.models.participant import Participant
import random
import string

def generate_team_code():
    """Generate unique team code"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def create_team(db: Session, team_name: str, track: str, leader_id: int):
    """Create a new team with leader"""
    # Generate unique code
    while True:
        code = generate_team_code()
        if not db.query(Team).filter(Team.code == code).first():
            break
    
    db_team = Team(
        name=team_name,
        code=code,
        track=track
    )
    db.add(db_team)
    db.commit()
    db.refresh(db_team)
    
    # Update participant to be team leader
    participant = db.query(Participant).filter(Participant.id == leader_id).first()
    if participant:
        participant.team_id = db_team.id
        participant.is_team_lead = True
        db.commit()
    
    return db_team

def join_team(db: Session, team_code: str, participant_id: int):
    """Join existing team using code"""
    team = db.query(Team).filter(Team.code == team_code).first()
    if not team:
        raise ValueError("Invalid team code")
    
    # Check team size limit
    current_members = db.query(Participant).filter(Participant.team_id == team.id).count()
    from app.config import settings
    if current_members >= settings.TEAM_MAX_SIZE:
        raise ValueError("Team is full")
    
    # Update participant
    participant = db.query(Participant).filter(Participant.id == participant_id).first()
    if participant:
        participant.team_id = team.id
        db.commit()
    
    return team

def get_team_by_code(db: Session, code: str):
    """Get team by code"""
    return db.query(Team).filter(Team.code == code).first()

def get_team_members(db: Session, team_id: int):
    """Get all team members"""
    return db.query(Participant).filter(Participant.team_id == team_id).all()

def get_team_with_payment_status(db: Session, team_id: int):
    """Get team details with payment status"""
    from app.crud.payment import get_team_payment_status
    
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        return None
    
    payment_status = get_team_payment_status(db, team_id)
    
    return {
        'team': team,
        'payment_status': payment_status,
        'all_paid': payment_status['paid_members'] == payment_status['total_members']
    }

def can_team_participate(db: Session, team_id: int) -> bool:
    """Check if all team members have paid"""
    from app.crud.payment import get_team_payment_status
    
    status = get_team_payment_status(db, team_id)
    return status['paid_members'] == status['total_members']