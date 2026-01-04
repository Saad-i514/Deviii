from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db
from app.auth.dependencies import get_current_ambassador
from app.models.participant import Participant
from app.models.user import User
from app.models.payment import Payment, PaymentStatus, PaymentMethod
from app.crud.payment import verify_cash_payment, search_payments
from app.utils.email import email_service
from app.utils.qr_code import generate_qr_code

router = APIRouter()

class ParticipantSearch(BaseModel):
    email: Optional[str] = None
    student_id: Optional[str] = None

class CashVerification(BaseModel):
    participant_id: int
    amount_collected: float
    notes: Optional[str] = None

class ParticipantInfo(BaseModel):
    id: int
    name: str
    email: str
    university: str
    student_id: str
    track: str
    team: Optional[str]
    payment_status: str
    payment_method: Optional[str]
    amount: Optional[float]

@router.post("/search", response_model=List[ParticipantInfo])
def search_participants(
    search_data: ParticipantSearch,
    current_ambassador = Depends(get_current_ambassador),
    db: Session = Depends(get_db)
):
    """
    Search for participants by email or student ID
    """
    if not search_data.email and not search_data.student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either email or student_id must be provided"
        )
    
    query = db.query(Participant).join(User)
    
    if search_data.email:
        query = query.filter(User.email.ilike(f"%{search_data.email}%"))
    
    if search_data.student_id:
        query = query.filter(Participant.student_id.ilike(f"%{search_data.student_id}%"))
    
    participants = query.limit(10).all()  # Limit results
    
    result = []
    for participant in participants:
        payment_info = {
            "status": "unpaid",
            "method": None,
            "amount": None
        }
        
        if participant.payment:
            payment_info = {
                "status": participant.payment.status.value,
                "method": participant.payment.payment_method.value,
                "amount": participant.payment.amount
            }
        
        result.append(ParticipantInfo(
            id=participant.id,
            name=participant.user.full_name,
            email=participant.user.email,
            university=participant.user.university or "Not specified",
            student_id=participant.student_id,
            track=participant.track.value,
            team=participant.team.name if participant.team else None,
            payment_status=payment_info["status"],
            payment_method=payment_info["method"],
            amount=payment_info["amount"]
        ))
    
    return result

@router.get("/participant/{participant_id}", response_model=ParticipantInfo)
def get_participant_details(
    participant_id: int,
    current_ambassador = Depends(get_current_ambassador),
    db: Session = Depends(get_db)
):
    """
    Get detailed participant information
    """
    participant = db.query(Participant).join(User).filter(
        Participant.id == participant_id
    ).first()
    
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found"
        )
    
    payment_info = {
        "status": "unpaid",
        "method": None,
        "amount": None
    }
    
    if participant.payment:
        payment_info = {
            "status": participant.payment.status.value,
            "method": participant.payment.payment_method.value,
            "amount": participant.payment.amount
        }
    
    return ParticipantInfo(
        id=participant.id,
        name=participant.user.full_name,
        email=participant.user.email,
        university=participant.user.university or "Not specified",
        student_id=participant.student_id,
        track=participant.track.value,
        team=participant.team.name if participant.team else None,
        payment_status=payment_info["status"],
        payment_method=payment_info["method"],
        amount=payment_info["amount"]
    )

@router.post("/verify-cash/{participant_id}")
async def verify_cash_payment_endpoint(
    participant_id: int,
    verification: CashVerification,
    current_ambassador = Depends(get_current_ambassador),
    db: Session = Depends(get_db)
):
    """
    Verify cash payment collection
    """
    # Get participant
    participant = db.query(Participant).join(User).filter(
        Participant.id == participant_id
    ).first()
    
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found"
        )
    
    # Check if participant has a cash payment pending
    if not participant.payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No payment record found for this participant"
        )
    
    if participant.payment.payment_method != PaymentMethod.CASH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This participant did not select cash payment method"
        )
    
    if participant.payment.status != PaymentStatus.PENDING_CASH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment status is {participant.payment.status.value}, cannot verify"
        )
    
    # Verify the payment
    payment = verify_cash_payment(
        db=db,
        participant_id=participant_id,
        ambassador_id=current_ambassador.id
    )
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify payment"
        )
    
    # Generate QR code
    qr_path = generate_qr_code(
        participant_id=participant.id,
        user_name=participant.user.full_name,
        email=participant.user.email,
        track=participant.track.value,
        team_name=participant.team.name if participant.team else None
    )
    
    # Send confirmation email with QR code
    await email_service.send_payment_verified_email(
        user_name=participant.user.full_name,
        email=participant.user.email,
        track=participant.track.value,
        qr_code_path=qr_path
    )
    
    return {
        "message": "Cash payment verified successfully",
        "payment_id": payment.id,
        "participant_name": participant.user.full_name,
        "amount": payment.amount,
        "verified_at": payment.verified_at,
        "qr_code_generated": True
    }

@router.get("/pending-cash", response_model=List[ParticipantInfo])
def get_pending_cash_payments(
    current_ambassador = Depends(get_current_ambassador),
    db: Session = Depends(get_db)
):
    """
    Get all participants with pending cash payments
    """
    participants = db.query(Participant).join(User).join(Payment).filter(
        Payment.payment_method == PaymentMethod.CASH,
        Payment.status == PaymentStatus.PENDING_CASH
    ).all()
    
    result = []
    for participant in participants:
        result.append(ParticipantInfo(
            id=participant.id,
            name=participant.user.full_name,
            email=participant.user.email,
            university=participant.user.university or "Not specified",
            student_id=participant.student_id,
            track=participant.track.value,
            team=participant.team.name if participant.team else None,
            payment_status=participant.payment.status.value,
            payment_method=participant.payment.payment_method.value,
            amount=participant.payment.amount
        ))
    
    return result

@router.get("/my-verifications")
def get_my_verifications(
    current_ambassador = Depends(get_current_ambassador),
    db: Session = Depends(get_db)
):
    """
    Get payments verified by current ambassador
    """
    payments = db.query(Payment).join(Participant).join(User).filter(
        Payment.verified_by == current_ambassador.id,
        Payment.status == PaymentStatus.VERIFIED
    ).all()
    
    result = []
    for payment in payments:
        participant = payment.participant
        result.append({
            "payment_id": payment.id,
            "participant_name": participant.user.full_name,
            "participant_email": participant.user.email,
            "student_id": participant.student_id,
            "track": participant.track.value,
            "amount": payment.amount,
            "verified_at": payment.verified_at,
            "payment_method": payment.payment_method.value
        })
    
    return {
        "verifications": result,
        "total_verified": len(result),
        "total_amount": sum(p.amount for p in payments)
    }

@router.get("/stats")
def get_ambassador_stats(
    current_ambassador = Depends(get_current_ambassador),
    db: Session = Depends(get_db)
):
    """
    Get statistics for current ambassador
    """
    # Total verifications by this ambassador
    total_verifications = db.query(Payment).filter(
        Payment.verified_by == current_ambassador.id,
        Payment.status == PaymentStatus.VERIFIED
    ).count()
    
    # Total amount collected
    total_amount = db.query(db.func.sum(Payment.amount)).filter(
        Payment.verified_by == current_ambassador.id,
        Payment.status == PaymentStatus.VERIFIED
    ).scalar() or 0
    
    # Verifications today
    today = datetime.now().date()
    today_verifications = db.query(Payment).filter(
        Payment.verified_by == current_ambassador.id,
        Payment.status == PaymentStatus.VERIFIED,
        db.func.date(Payment.verified_at) == today
    ).count()
    
    # Pending cash payments (system-wide)
    pending_cash = db.query(Payment).filter(
        Payment.payment_method == PaymentMethod.CASH,
        Payment.status == PaymentStatus.PENDING_CASH
    ).count()
    
    return {
        "ambassador_name": current_ambassador.full_name,
        "total_verifications": total_verifications,
        "total_amount_collected": float(total_amount),
        "verifications_today": today_verifications,
        "pending_cash_payments": pending_cash
    }

@router.get("/audit-log")
def get_audit_log(
    current_ambassador = Depends(get_current_ambassador),
    db: Session = Depends(get_db)
):
    """
    Get audit log of ambassador's actions
    """
    # Get all payments verified by this ambassador with timestamps
    payments = db.query(Payment).join(Participant).join(User).filter(
        Payment.verified_by == current_ambassador.id,
        Payment.status == PaymentStatus.VERIFIED
    ).order_by(Payment.verified_at.desc()).all()
    
    audit_entries = []
    for payment in payments:
        participant = payment.participant
        audit_entries.append({
            "action": "cash_payment_verified",
            "timestamp": payment.verified_at,
            "participant_id": participant.id,
            "participant_name": participant.user.full_name,
            "participant_email": participant.user.email,
            "student_id": participant.student_id,
            "amount": payment.amount,
            "payment_id": payment.id
        })
    
    return {
        "ambassador": current_ambassador.full_name,
        "audit_entries": audit_entries,
        "total_entries": len(audit_entries)
    }