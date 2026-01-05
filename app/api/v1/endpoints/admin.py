from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db
from app.auth.dependencies import get_current_admin
from app.models.user import User, UserRole
from app.models.participant import Participant, Track
from app.models.team import Team
from app.models.payment import Payment, PaymentStatus
from app.models.event import CheckIn
from app.crud.user import create_user, update_user_role
from app.schemas.user import UserCreate
from app.utils.qr_code import verify_qr_code

router = APIRouter()

class AdminDashboard(BaseModel):
    total_registrations: int
    total_teams: int
    payment_summary: dict
    track_breakdown: dict

class UserRoleUpdate(BaseModel):
    user_id: int
    role: UserRole

class CreateAdminUser(BaseModel):
    email: str
    password: str
    full_name: str
    role: UserRole

class CheckInCreate(BaseModel):
    qr_data: str
    event_type: str

@router.get("/dashboard", response_model=AdminDashboard)
def get_admin_dashboard(
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Admin dashboard - total registrations, teams, payment tracking, track breakdown
    """
    # Total registrations
    total_registrations = db.query(Participant).count()
    
    # Total teams
    total_teams = db.query(Team).count()
    
    # Payment summary - Total Online and Total Cash
    online_verified = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.payment_method == "online",
        Payment.status == PaymentStatus.VERIFIED
    ).scalar()
    
    cash_verified = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(Payment.payment_method == "cash", Payment.status == PaymentStatus.VERIFIED).scalar()
    
    payment_summary = {
        'total_online': float(online_verified),
        'total_cash': float(cash_verified),
        'total_collected': float(online_verified + cash_verified)
    }
    
    # Track breakdown
    track_stats = db.query(
        Participant.track,
        func.count(Participant.id).label('count')
    ).group_by(Participant.track).all()
    
    track_breakdown = {
        track.value: count for track, count in track_stats
    }
    
    return AdminDashboard(
        total_registrations=total_registrations,
        total_teams=total_teams,
        payment_summary=payment_summary,
        track_breakdown=track_breakdown
    )

@router.get("/participants")
def get_all_participants(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    track: Optional[Track] = None,
    university: Optional[str] = None,
    payment_status: Optional[PaymentStatus] = None,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get all participants with filtering - for editing registrations and teams
    """
    query = db.query(Participant).join(User)
    
    # Apply filters
    if track:
        query = query.filter(Participant.track == track)
    
    if university:
        query = query.filter(User.university.ilike(f"%{university}%"))
    
    if payment_status:
        query = query.join(Payment).filter(Payment.status == payment_status)
    
    total = query.count()
    participants = query.offset(skip).limit(limit).all()
    
    result = []
    for participant in participants:
        payment_info = None
        if participant.payment:
            payment_info = {
                "status": participant.payment.status.value,
                "amount": participant.payment.amount,
                "method": participant.payment.payment_method.value,
                "verified_at": participant.payment.verified_at
            }
        
        result.append({
            "id": participant.id,
            "name": participant.user.full_name,
            "email": participant.user.email,
            "university": participant.user.university,
            "student_id": participant.student_id,
            "track": participant.track.value,
            "team": participant.team.name if participant.team else None,
            "is_team_lead": participant.is_team_lead,
            "payment": payment_info,
            "created_at": participant.user.created_at
        })
    
    return {
        "participants": result,
        "total": total
    }

@router.post("/create-user", response_model=dict)
def create_admin_user(
    user_data: CreateAdminUser,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Create admin, ambassador, or registration team user
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user_create = UserCreate(
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name
    )
    
    user = create_user(db, user_create)
    
    # Update role
    update_user_role(db, user.id, user_data.role.value)
    
    return {
        "message": f"{user_data.role.value} user created successfully",
        "user_id": user.id,
        "email": user.email,
        "role": user_data.role.value
    }

@router.put("/update-user-role")
def update_user_role_endpoint(
    role_update: UserRoleUpdate,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Update user role
    """
    user = update_user_role(db, role_update.user_id, role_update.role.value)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "message": "User role updated successfully",
        "user_id": user.id,
        "new_role": user.role.value
    }

@router.get("/users")
def get_all_users(
    role: Optional[UserRole] = None,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get all users - for managing admin, registration team, and ambassador accounts
    """
    query = db.query(User)
    
    if role:
        query = query.filter(User.role == role)
    
    users = query.all()
    
    return [
        {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active,
            "created_at": user.created_at
        }
        for user in users
    ]

@router.get("/export/participants")
def export_participants(
    format: str = Query("csv", pattern="^(csv|excel)$"),
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Export full attendee list as CSV/Excel for Opening Ceremony check-in
    """
    import pandas as pd
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    
    # Get all participants with related data
    participants = db.query(Participant).join(User).all()
    
    data = []
    for participant in participants:
        payment_info = {
            "payment_status": "unpaid",
            "payment_method": None,
            "amount": 0,
            "verified_at": None
        }
        
        if participant.payment:
            payment_info = {
                "payment_status": participant.payment.status.value,
                "payment_method": participant.payment.payment_method.value,
                "amount": participant.payment.amount,
                "verified_at": participant.payment.verified_at
            }
        
        data.append({
            "Name": participant.user.full_name,
            "Email": participant.user.email,
            "University": participant.user.university,
            "Phone": participant.user.phone_number,
            "Student ID": participant.student_id,
            "CNIC": participant.cnic,
            "Track": participant.track.value,
            "Team": participant.team.name if participant.team else "Individual",
            "Is Team Lead": participant.is_team_lead,
            "T-Shirt Size": participant.tshirt_size.value,
            "Emergency Contact": participant.emergency_contact,
            "Dietary Requirements": participant.dietary_requirements,
            "Payment Status": payment_info["payment_status"],
            "Payment Method": payment_info["payment_method"],
            "Amount Paid": payment_info["amount"],
            "Payment Verified At": payment_info["verified_at"],
            "Registered At": participant.user.created_at
        })
    
    df = pd.DataFrame(data)
    
    if format == "excel":
        output = BytesIO()
        try:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Participants')
            output.seek(0)
            
            return StreamingResponse(
                BytesIO(output.getvalue()),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": "attachment; filename=devcon26_participants.xlsx"}
            )
        except Exception as e:
            # Fallback to CSV if Excel fails
            csv_data = df.to_csv(index=False)
            return StreamingResponse(
                iter([csv_data]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=devcon26_participants_fallback.csv"}
            )
    else:
        csv_data = df.to_csv(index=False)
        return StreamingResponse(
            iter([csv_data]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=devcon26_participants.csv"}
        )

@router.post("/check-in")
def check_in_participant(
    check_in_data: CheckInCreate,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Check in a participant using QR code (Admin only)
    """
    # Verify QR code
    qr_result = verify_qr_code(check_in_data.qr_data)
    if not qr_result["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid QR code: {qr_result.get('error', 'Unknown error')}"
        )
    
    qr_data = qr_result["data"]
    participant_id = qr_data["participant_id"]
    
    # Get participant
    participant = db.query(Participant).filter(Participant.id == participant_id).first()
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found"
        )
    
    # Check if participant has paid
    if not participant.payment or participant.payment.status != PaymentStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Participant payment not verified"
        )
    
    # Check if already checked in for this event
    existing_checkin = db.query(CheckIn).filter(
        CheckIn.participant_id == participant_id,
        CheckIn.event_type == check_in_data.event_type
    ).first()
    
    if existing_checkin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Participant already checked in for this event"
        )
    
    # Create check-in record
    check_in = CheckIn(
        participant_id=participant_id,
        event_type=check_in_data.event_type,
        checked_by=current_admin.id
    )
    
    db.add(check_in)
    db.commit()
    db.refresh(check_in)
    
    return {
        "message": "Check-in successful",
        "participant_name": participant.user.full_name,
        "event_type": check_in_data.event_type,
        "checked_in_at": check_in.checked_in_at
    }

@router.post("/verify-qr")
def verify_qr_endpoint(
    qr_data: str,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Verify QR code and return participant info (Admin only)
    """
    # Verify QR code
    qr_result = verify_qr_code(qr_data)
    if not qr_result["valid"]:
        return {
            "valid": False,
            "error": qr_result.get("error", "Invalid QR code")
        }
    
    qr_data_parsed = qr_result["data"]
    participant_id = qr_data_parsed["participant_id"]
    
    # Get participant details
    participant = db.query(Participant).join(User).filter(
        Participant.id == participant_id
    ).first()
    
    if not participant:
        return {
            "valid": False,
            "error": "Participant not found"
        }
    
    # Check payment status
    payment_verified = (
        participant.payment and 
        participant.payment.status == PaymentStatus.VERIFIED
    )
    
    if not payment_verified:
        return {
            "valid": False,
            "error": "Payment not verified"
        }
    
    return {
        "valid": True,
        "participant_id": participant_id,
        "participant_name": participant.user.full_name,
        "track": participant.track.value,
        "team": participant.team.name if participant.team else None,
        "payment_verified": True
    }

@router.post("/verify-online/{payment_id}")
async def verify_online_payment(
    payment_id: int,
    approve: bool = Query(True, description="Approve (True) or reject (False)"),
    remarks: Optional[str] = None,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Verify or reject an online payment (Admin only)
    """
    from app.utils.email import email_service
    from app.utils.qr_code import generate_qr_code
    
    # Get payment with participant and user info
    payment = db.query(Payment).join(Participant).join(User).filter(
        Payment.id == payment_id
    ).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    if payment.payment_method != "online":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This is not an online payment"
        )
    
    participant = payment.participant
    user = participant.user
    
    # Update payment status
    if approve:
        payment.status = PaymentStatus.VERIFIED
        payment.verified_by = current_admin.id
        payment.verified_at = datetime.now()
        
        # Generate QR code for approved payment
        qr_path = generate_qr_code(
            participant_id=participant.id,
            user_name=user.full_name,
            email=user.email,
            track=participant.track.value,
            team_name=participant.team.name if participant.team else None
        )
        
        # Send approval email with QR code
        try:
            await email_service.send_payment_verified_email(
                user_name=user.full_name,
                email=user.email,
                track=participant.track.value,
                qr_code_path=qr_path
            )
            email_sent = True
        except Exception as e:
            print(f"Failed to send approval email: {e}")
            email_sent = False
            
    else:
        payment.status = PaymentStatus.REJECTED
        
        # Send rejection email
        try:
            await email_service.send_payment_rejected_email(
                user_name=user.full_name,
                email=user.email,
                reason=remarks or "Payment receipt could not be verified"
            )
            email_sent = True
        except Exception as e:
            print(f"Failed to send rejection email: {e}")
            email_sent = False
    
    db.commit()
    db.refresh(payment)
    
    return {
        "message": f"Payment {'approved' if approve else 'rejected'} successfully",
        "payment_id": payment.id,
        "participant_name": user.full_name,
        "participant_email": user.email,
        "status": payment.status.value,
        "verified_by": payment.verified_by,
        "verified_at": payment.verified_at,
        "remarks": remarks,
        "email_sent": email_sent,
        "qr_code_generated": approve and email_sent
    }
@router.post("/create-participant-profile")
def create_admin_participant_profile(
    participant_data: dict,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Allow admin to create a participant profile for themselves
    """
    from app.crud.participant import create_participant
    from app.schemas.participant import ParticipantCreate
    
    # Check if admin already has participant profile
    existing_participant = db.query(Participant).filter(
        Participant.user_id == current_admin.id
    ).first()
    
    if existing_participant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin already has a participant profile"
        )
    
    # Create participant profile for admin
    participant_create = ParticipantCreate(**participant_data)
    participant = create_participant(db, participant_create, current_admin.id)
    
    return {
        "message": "Participant profile created for admin",
        "participant_id": participant.id,
        "admin_can_now_access_participant_endpoints": True
    }
@router.post("/create-ambassador-profile")
def create_ambassador_profile_for_user(
    user_email: str,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Allow admin to grant ambassador privileges to any user (including themselves)
    """
    # Find the user
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update user role to ambassador (or keep existing if admin)
    if user.role == UserRole.ADMIN:
        # Admin keeps admin role but can now access ambassador endpoints
        message = f"Admin {user.full_name} can now access ambassador endpoints"
    else:
        user.role = UserRole.AMBASSADOR
        db.commit()
        message = f"User {user.full_name} is now an ambassador"
    
    return {
        "message": message,
        "user_id": user.id,
        "email": user.email,
        "role": user.role.value,
        "can_access_ambassador_endpoints": True
    }

@router.post("/create-registration-team-profile")
def create_registration_team_profile_for_user(
    user_email: str,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Allow admin to grant registration team privileges to any user
    """
    # Find the user
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update user role to registration team (or keep existing if admin)
    if user.role == UserRole.ADMIN:
        message = f"Admin {user.full_name} can now access registration team endpoints"
    else:
        user.role = UserRole.REGISTRATION_TEAM
        db.commit()
        message = f"User {user.full_name} is now part of registration team"
    
    return {
        "message": message,
        "user_id": user.id,
        "email": user.email,
        "role": user.role.value,
        "can_access_registration_team_endpoints": True
    }

@router.post("/grant-multi-role-access")
def grant_multi_role_access(
    user_email: str,
    target_role: UserRole,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Grant multi-role access to a user
    """
    # Find the user
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update role
    old_role = user.role.value
    user.role = target_role
    db.commit()
    
    return {
        "message": f"User role updated from {old_role} to {target_role.value}",
        "user_id": user.id,
        "email": user.email,
        "old_role": old_role,
        "new_role": user.role.value,
        "multi_role_access": True,
        "can_access": {
            "participant_endpoints": True,
            "ambassador_endpoints": target_role in [UserRole.AMBASSADOR, UserRole.ADMIN],
            "registration_team_endpoints": target_role in [UserRole.REGISTRATION_TEAM, UserRole.ADMIN],
            "admin_endpoints": target_role == UserRole.ADMIN
        }
    }