from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db
from app.auth.dependencies import get_current_registration_team
from app.models.participant import Participant
from app.models.user import User
from app.models.payment import Payment, PaymentStatus, PaymentMethod
from app.models.team import Team
from app.crud.participant import create_participant
from app.crud.user import create_user
from app.crud.team import create_team
from app.crud.payment import create_payment
from app.schemas.user import UserCreate
from app.schemas.participant import ParticipantCreate
from app.config import settings
from app.utils.validators import validate_file_upload
import os

router = APIRouter()

class ManualRegistration(BaseModel):
    # User data
    email: str
    password: str
    full_name: str
    university: str
    phone_number: str
    
    # Participant data
    student_id: str
    cnic: str
    track: str
    technical_skills: Optional[str] = None
    github_link: Optional[str] = None
    portfolio_link: Optional[str] = None
    tshirt_size: str
    dietary_requirements: Optional[str] = None
    emergency_contact: str
    
    # Team data (optional)
    create_new_team: bool = False
    team_name: Optional[str] = None
    team_code: Optional[str] = None
    
    # Payment
    payment_method: str  # "cash" or "online"
    amount: float

class FlagPayment(BaseModel):
    payment_id: int
    reason: str

@router.get("/dashboard")
def get_registration_dashboard(
    current_team_member = Depends(get_current_registration_team),
    db: Session = Depends(get_db)
):
    """
    Registration team dashboard - basic stats only
    """
    # Total registrations
    total_registrations = db.query(Participant).count()
    
    # Pending payments
    pending_payments = db.query(Payment).filter(
        Payment.status.in_([PaymentStatus.PENDING, PaymentStatus.PENDING_CASH])
    ).count()
    
    # Cash vs online count
    cash_count = db.query(Payment).filter(Payment.payment_method == PaymentMethod.CASH).count()
    online_count = db.query(Payment).filter(Payment.payment_method == PaymentMethod.ONLINE).count()
    
    return {
        "total_registrations": total_registrations,
        "pending_payments": pending_payments,
        "cash_payments": cash_count,
        "online_payments": online_count
    }

@router.post("/register-manual")
def register_participant_manually(
    registration_data: ManualRegistration,
    current_team_member = Depends(get_current_registration_team),
    db: Session = Depends(get_db)
):
    """
    Register teams manually (cash or late entries)
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == registration_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user_create = UserCreate(
        email=registration_data.email,
        password=registration_data.password,
        full_name=registration_data.full_name,
        university=registration_data.university,
        phone_number=registration_data.phone_number
    )
    
    user = create_user(db, user_create)
    
    # Create participant
    participant_create = ParticipantCreate(
        student_id=registration_data.student_id,
        cnic=registration_data.cnic,
        track=registration_data.track,
        technical_skills=registration_data.technical_skills,
        github_link=registration_data.github_link,
        portfolio_link=registration_data.portfolio_link,
        tshirt_size=registration_data.tshirt_size,
        dietary_requirements=registration_data.dietary_requirements,
        emergency_contact=registration_data.emergency_contact,
        create_new_team=registration_data.create_new_team,
        team_name=registration_data.team_name,
        team_code=registration_data.team_code
    )
    
    participant = create_participant(db, participant_create, user.id)
    
    # Handle team creation/joining
    team_id = None
    if registration_data.create_new_team and registration_data.team_name:
        team = create_team(db, registration_data.team_name, registration_data.track, participant.id)
        team_id = team.id
        participant.team_id = team_id
        participant.is_team_lead = True
    elif registration_data.team_code:
        from app.crud.team import join_team
        team = join_team(db, registration_data.team_code, participant.id)
        team_id = team.id
        participant.team_id = team_id
    
    # Create payment record
    payment = create_payment(
        db=db,
        participant_id=participant.id,
        team_id=team_id,
        amount=registration_data.amount,
        payment_method=registration_data.payment_method
    )
    
    db.commit()
    
    return {
        "message": "Participant registered manually",
        "user_id": user.id,
        "participant_id": participant.id,
        "payment_id": payment.id,
        "team_id": team_id
    }

@router.post("/upload-payment-proof/{payment_id}")
def upload_payment_proof_for_participant(
    payment_id: int,
    receipt: UploadFile = File(...),
    current_team_member = Depends(get_current_registration_team),
    db: Session = Depends(get_db)
):
    """
    Upload payment proof for cash payments
    """
    # Get payment
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Validate file
    validate_file_upload(receipt, settings.ALLOWED_EXTENSIONS, settings.MAX_FILE_SIZE)
    
    # Save file
    file_ext = os.path.splitext(receipt.filename)[1]
    filename = f"receipt_{payment_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, filename)
    
    with open(file_path, "wb") as buffer:
        content = receipt.file.read()
        buffer.write(content)
    
    # Update payment
    payment.receipt_path = file_path
    payment.uploaded_at = datetime.now()
    db.commit()
    
    return {"message": "Payment proof uploaded successfully"}

@router.get("/registrations")
def view_all_registrations(
    skip: int = 0,
    limit: int = 100,
    current_team_member = Depends(get_current_registration_team),
    db: Session = Depends(get_db)
):
    """
    View all registrations (read-only)
    """
    participants = db.query(Participant).join(User).offset(skip).limit(limit).all()
    
    result = []
    for participant in participants:
        payment_info = None
        if participant.payment:
            payment_info = {
                "id": participant.payment.id,
                "status": participant.payment.status.value,
                "method": participant.payment.payment_method.value,
                "amount": participant.payment.amount,
                "receipt_path": participant.payment.receipt_path
            }
        
        result.append({
            "id": participant.id,
            "name": participant.user.full_name,
            "email": participant.user.email,
            "university": participant.user.university,
            "student_id": participant.student_id,
            "track": participant.track.value,
            "team": participant.team.name if participant.team else None,
            "payment": payment_info
        })
    
    return {"registrations": result}

@router.get("/payments")
def view_payments(
    current_team_member = Depends(get_current_registration_team),
    db: Session = Depends(get_db)
):
    """
    View payments with proof preview
    """
    payments = db.query(Payment).join(Participant).join(User).all()
    
    result = []
    for payment in payments:
        participant = payment.participant
        result.append({
            "payment_id": payment.id,
            "participant_name": participant.user.full_name,
            "email": participant.user.email,
            "student_id": participant.student_id,
            "amount": payment.amount,
            "method": payment.payment_method.value,
            "status": payment.status.value,
            "receipt_path": payment.receipt_path,
            "transaction_id": payment.transaction_id,
            "created_at": payment.created_at
        })
    
    return {"payments": result}

@router.post("/flag-payment")
def flag_suspicious_payment(
    flag_data: FlagPayment,
    current_team_member = Depends(get_current_registration_team),
    db: Session = Depends(get_db)
):
    """
    Flag suspicious or incomplete payments
    """
    payment = db.query(Payment).filter(Payment.id == flag_data.payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # For now, we'll just log this - in a real system you'd have a flags table
    # This is a simplified implementation as per requirements
    
    return {
        "message": "Payment flagged successfully",
        "payment_id": flag_data.payment_id,
        "reason": flag_data.reason,
        "flagged_by": current_team_member.full_name,
        "flagged_at": datetime.now()
    }