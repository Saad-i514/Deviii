from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr
import os

from app.database import get_db
from app.models.participant import Participant
from app.models.user import User
from app.models.payment import Payment, PaymentStatus
from app.crud.user import create_user, get_user_by_email
from app.crud.participant import create_participant
from app.crud.team import create_team, join_team
from app.crud.payment import create_payment
from app.schemas.user import UserCreate
from app.schemas.participant import ParticipantCreate
from app.config import settings
from app.utils.validators import validate_file_upload
from app.utils.email import email_service

router = APIRouter()

class PublicRegistration(BaseModel):
    # User data
    email: EmailStr
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

class PaymentMethodSelection(BaseModel):
    email: EmailStr
    payment_method: str  # "online" or "cash"

class OnlinePaymentUpload(BaseModel):
    email: EmailStr
    transaction_id: str

class RegistrationStatusCheck(BaseModel):
    email: EmailStr

@router.post("/register")
async def public_registration(
    registration_data: PublicRegistration,
    db: Session = Depends(get_db)
):
    """
    Public registration endpoint (no login required)
    """
    try:
        # Check if email already exists
        existing_user = get_user_by_email(db, registration_data.email)
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
        team_code = None
        
        if registration_data.create_new_team and registration_data.team_name:
            team = create_team(db, registration_data.team_name, registration_data.track, participant.id)
            team_id = team.id
            team_code = team.code
            participant.team_id = team_id
            participant.is_team_lead = True
        elif registration_data.team_code:
            team = join_team(db, registration_data.team_code, participant.id)
            team_id = team.id
            team_code = team.code
            participant.team_id = team_id
        
        db.commit()
        
        # Send registration pending email
        # await email_service.send_registration_pending_email(
        #     user_name=user.full_name,
        #     email=user.email,
        #     track=registration_data.track
        # )
        
        return {
            "message": "Registration successful. Please complete payment to finalize.",
            "user_id": user.id,
            "participant_id": participant.id,
            "team_code": team_code,
            "next_step": "Select payment method and complete payment"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Registration error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@router.post("/select-payment-method")
def select_payment_method(
    payment_data: PaymentMethodSelection,
    db: Session = Depends(get_db)
):
    """
    Select payment method (online or cash)
    """
    # Get user and participant
    user = get_user_by_email(db, payment_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    participant = db.query(Participant).filter(Participant.user_id == user.id).first()
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant profile not found"
        )
    
    # Check if payment already exists
    existing_payment = db.query(Payment).filter(Payment.participant_id == participant.id).first()
    if existing_payment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment method already selected"
        )
    
    # Create payment record
    payment = create_payment(
        db=db,
        participant_id=participant.id,
        team_id=participant.team_id,
        amount=settings.REGISTRATION_FEE,
        payment_method=payment_data.payment_method
    )
    
    if payment_data.payment_method == "cash":
        message = "Cash payment selected. Please visit a Devcon Ambassador on campus to complete payment."
    else:
        message = "Online payment selected. Please upload your payment receipt."
    
    return {
        "message": message,
        "payment_id": payment.id,
        "payment_method": payment_data.payment_method,
        "amount": settings.REGISTRATION_FEE
    }

@router.post("/upload-payment-receipt")
async def upload_payment_receipt_public(
    email: str = Form(...),
    transaction_id: str = Form(...),
    receipt: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload payment receipt (public endpoint)
    """
    # Get user and participant
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    participant = db.query(Participant).filter(Participant.user_id == user.id).first()
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant profile not found"
        )
    
    # Get payment
    payment = db.query(Payment).filter(Payment.participant_id == participant.id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment record not found. Please select payment method first."
        )
    
    if payment.payment_method != "online":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This payment is not set for online method"
        )
    
    # Validate file
    validate_file_upload(receipt, settings.ALLOWED_EXTENSIONS, settings.MAX_FILE_SIZE)
    
    # Save file
    file_ext = os.path.splitext(receipt.filename)[1]
    filename = f"receipt_{participant.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, filename)
    
    with open(file_path, "wb") as buffer:
        content = await receipt.read()
        buffer.write(content)
    
    # Update payment
    payment.transaction_id = transaction_id
    payment.receipt_path = file_path
    payment.uploaded_at = datetime.now()
    db.commit()
    
    return {
        "message": "Payment receipt uploaded successfully. Awaiting verification.",
        "status": "pending_verification"
    }

@router.post("/check-status")
def check_registration_status(
    status_check: RegistrationStatusCheck,
    db: Session = Depends(get_db)
):
    """
    Check registration status via email
    """
    # Get user
    user = get_user_by_email(db, status_check.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registration found for this email"
        )
    
    # Get participant
    participant = db.query(Participant).filter(Participant.user_id == user.id).first()
    if not participant:
        return {
            "status": "user_created",
            "message": "User account created but participant profile incomplete"
        }
    
    # Get payment status
    payment = db.query(Payment).filter(Payment.participant_id == participant.id).first()
    
    payment_status = "no_payment"
    payment_method = None
    
    if payment:
        payment_status = payment.status.value
        payment_method = payment.payment_method.value
    
    # Get team info
    team_info = None
    if participant.team:
        team_info = {
            "name": participant.team.name,
            "code": participant.team.code,
            "is_lead": participant.is_team_lead
        }
    
    return {
        "registration_status": "complete" if participant else "incomplete",
        "payment_status": payment_status,
        "payment_method": payment_method,
        "track": participant.track.value,
        "team": team_info,
        "can_enter_event": payment_status == "verified"
    }

@router.get("/tracks")
def get_available_tracks():
    """
    Get list of available tracks
    """
    return {
        "tracks": [
            {
                "id": "programming",
                "name": "Programming",
                "description": "Build real solutions under pressure. Code, debug, and ship functional software within strict time limits."
            },
            {
                "id": "ideathon", 
                "name": "Ideathon",
                "description": "Where business meets technology. Pitch your innovative startup ideas to a panel of industry experts."
            },
            {
                "id": "competitive_programming",
                "name": "Competitive Programming", 
                "description": "Think fast, code faster. Solve algorithmic challenges where efficiency and accuracy decide the leaderboard."
            },
            {
                "id": "gaming",
                "name": "Gaming",
                "description": "Skill. Strategy. Victory. Compete in high-stakes matches and fight your way to the finals."
            },
            {
                "id": "socialite",
                "name": "Socialite",
                "description": "Connect beyond code. Network, collaborate, and experience Devcon's social side."
            }
        ]
    }

@router.get("/universities")
def get_universities():
    """
    Get list of supported universities
    """
    return {
        "universities": [
            "University of Engineering and Technology (UET) Lahore",
            "Lahore University of Management Sciences (LUMS)",
            "Information Technology University (ITU) Punjab",
            "University of Central Punjab (UCP)",
            "Punjab University College of Information Technology (PUCIT)",
            "Forman Christian College (FCCU)",
            "Government College University (GCU) Lahore",
            "National University of Computer and Emerging Sciences (FAST-NUCES)",
            "Comsats University Islamabad (CUI)",
            "University of Management and Technology (UMT)",
            "Superior University",
            "Lahore Leads University",
            "Other"
        ]
    }

@router.get("/stats")
def get_public_stats(db: Session = Depends(get_db)):
    """
    Get public registration statistics
    """
    from sqlalchemy import func
    
    # Total registrations
    total_registrations = db.query(Participant).count()
    
    # Registrations by track
    track_stats = db.query(
        Participant.track,
        func.count(Participant.id).label('count')
    ).group_by(Participant.track).all()
    
    # Payment statistics
    total_payments = db.query(Payment).filter(
        Payment.status == PaymentStatus.VERIFIED
    ).count()
    
    # Team statistics
    total_teams = db.query(func.count(func.distinct(Participant.team_id))).filter(
        Participant.team_id.isnot(None)
    ).scalar() or 0
    
    # University statistics (top 5)
    university_stats = db.query(
        User.university,
        func.count(User.id).label('count')
    ).join(Participant).group_by(User.university).order_by(
        func.count(User.id).desc()
    ).limit(5).all()
    
    return {
        "total_registrations": total_registrations,
        "verified_payments": total_payments,
        "total_teams": total_teams,
        "tracks": {track.value: count for track, count in track_stats},
        "top_universities": [
            {"name": uni, "count": count} for uni, count in university_stats
        ],
        "registration_completion_rate": round(
            (total_payments / total_registrations * 100) if total_registrations > 0 else 0, 2
        )
    }