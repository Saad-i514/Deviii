from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.auth.dependencies import (
    get_current_user,
    get_current_participant,
    get_current_admin,
    get_current_ambassador,
    get_current_registration_team
)
from app.schemas.payment import (
    PaymentInDB,
    PaymentVerification,
    PaymentSummary,
    PaymentDashboard,
    PaymentWithParticipant,
    PaymentReceiptUpload,
    PaymentUpdate,
    PaymentStatus
)
from app.crud.payment import (
    create_payment,
    get_payment_by_participant,
    get_payment_by_id,
    verify_online_payment,
    get_payments_summary,
    get_pending_verifications,
    get_recent_payments,
    search_payments,
    verify_cash_payment,
    update_payment_status,
    get_team_payment_status
)
from app.crud.participant import get_participant_by_user_id
from app.config import settings
from app.utils.validators import validate_file_upload
from app.utils.email import email_service
import os
from app.utils.email import email_service
from app.utils.qr_code import generate_qr_code

router = APIRouter()

# ===== PUBLIC/PARTICIPANT ENDPOINTS =====

@router.post("/upload-receipt", response_model=PaymentInDB)
async def upload_payment_receipt(
    payment_data: PaymentReceiptUpload,
    receipt: UploadFile = File(...),
    current_user = Depends(get_current_participant),
    db: Session = Depends(get_db)
):
    """
    Upload payment receipt for online payment
    """
    # Validate file
    validate_file_upload(receipt, settings.ALLOWED_EXTENSIONS, settings.MAX_FILE_SIZE)
    
    # Check if participant already has a payment
    existing_payment = get_payment_by_participant(db, current_user.id)
    if existing_payment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment already exists for this participant"
        )
    
    # Save receipt file
    file_ext = os.path.splitext(receipt.filename)[1]
    filename = f"receipt_{current_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, filename)
    
    with open(file_path, "wb") as buffer:
        content = await receipt.read()
        buffer.write(content)
    
    # Get participant's team_id
    participant = get_participant_by_user_id(db, current_user.id)
    
    # Create payment record
    payment = create_payment(
        db=db,
        participant_id=current_user.id,
        team_id=participant.team_id if participant else None,
        amount=payment_data.amount,
        payment_method="online",
        transaction_id=payment_data.transaction_id,
        receipt_path=file_path
    )
    
    # Send confirmation email
    await email_service.send_registration_pending_email(
        user_name=current_user.user.full_name,
        email=current_user.user.email,
        track=participant.track.value if participant else "Unknown"
    )
    
    return payment

@router.post("/select-cash")
def select_cash_payment(
    current_user = Depends(get_current_participant),
    db: Session = Depends(get_db)
):
    """
    Select cash payment option (sets status to pending_cash)
    """
    # Check if participant already has a payment
    existing_payment = get_payment_by_participant(db, current_user.id)
    if existing_payment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment already exists for this participant"
        )
    
    # Get participant's team_id
    participant = get_participant_by_user_id(db, current_user.id)
    
    # Create cash payment record
    payment = create_payment(
        db=db,
        participant_id=current_user.id,
        team_id=participant.team_id if participant else None,
        amount=settings.REGISTRATION_FEE,
        payment_method="cash"
    )
    
    return {
        "message": "Cash payment selected. Please visit a Devcon Ambassador on campus to complete payment.",
        "payment_id": payment.id,
        "status": payment.status
    }

@router.get("/my-payment", response_model=PaymentInDB)
def get_my_payment(
    current_user = Depends(get_current_participant),
    db: Session = Depends(get_db)
):
    """
    Get current user's payment status
    """
    payment = get_payment_by_participant(db, current_user.id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No payment record found"
        )
    return payment

@router.get("/team-payment-status/{team_id}")
def get_team_payment(
    team_id: int,
    current_user = Depends(get_current_participant),
    db: Session = Depends(get_db)
):
    """
    Get payment status for user's team
    """
    # Verify user belongs to this team
    participant = get_participant_by_user_id(db, current_user.id)
    if not participant or participant.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this team"
        )
    
    status = get_team_payment_status(db, team_id)
    return status

# ===== AMBASSADOR ENDPOINTS =====

@router.post("/verify-cash", response_model=PaymentInDB)
def verify_cash_payment_endpoint(
    verification: PaymentVerification,
    db: Session = Depends(get_db),
    ambassador = Depends(get_current_ambassador)
):
    """
    Verify cash payment (Ambassador only)
    """
    payment = verify_cash_payment(
        db=db,
        participant_id=verification.participant_id,
        ambassador_id=ambassador.id
    )
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found or not a cash payment"
        )
    
    # Log the verification (TODO: Implement audit logging)
    
    return payment

@router.get("/pending-cash", response_model=List[PaymentWithParticipant])
def get_pending_cash_payments(
    db: Session = Depends(get_db),
    ambassador = Depends(get_current_ambassador)
):
    """
    Get all pending cash payments
    """
    payments = search_payments(db, status=PaymentStatus.PENDING_CASH)
    return payments

# ===== REGISTRATION TEAM ENDPOINTS =====

@router.post("/register-cash", response_model=PaymentInDB)
def register_cash_payment_manual(
    participant_id: int,
    amount: float,
    db: Session = Depends(get_db),
    team_member = Depends(get_current_registration_team)
):
    """
    Register a cash payment manually (Registration team only)
    """
    # Check if participant already has a payment
    existing_payment = get_payment_by_participant(db, participant_id)
    if existing_payment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment already exists for this participant"
        )
    
    # Create cash payment record
    payment = create_payment(
        db=db,
        participant_id=participant_id,
        team_id=None,  # Will be updated when participant joins team
        amount=amount,
        payment_method="cash"
    )
    
    # Immediately verify (since cash is collected)
    payment = update_payment_status(
        db=db,
        payment_id=payment.id,
        status=PaymentStatus.VERIFIED,
        verified_by=team_member.id
    )
    
    return payment

# ===== ADMIN ENDPOINTS =====

@router.get("/dashboard", response_model=PaymentDashboard)
def get_payment_dashboard(
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin)
):
    """
    Get payment dashboard for admin
    """
    summary = get_payments_summary(db)
    recent_payments = get_recent_payments(db, limit=10)
    pending_verifications = get_pending_verifications()
    
    return PaymentDashboard(
        summary=PaymentSummary(**summary),
        recent_payments=recent_payments,
        pending_verifications=pending_verifications
    )

@router.post("/verify-online/{payment_id}", response_model=PaymentInDB)
def verify_online_payment_endpoint(
    payment_id: int,
    approve: bool = Query(True, description="Approve (True) or reject (False)"),
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin)
):
    """
    Verify or reject an online payment (Admin only)
    """
    payment = verify_online_payment(
        db=db,
        payment_id=payment_id,
        approve=approve,
        admin_id=admin.id
    )
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found or not an online payment"
        )
    
    # Send email notification
    # TODO: Implement email sending based on approval status
    
    return payment

@router.get("/search", response_model=List[PaymentWithParticipant])
def search_payments_endpoint(
    email: Optional[str] = None,
    student_id: Optional[str] = None,
    transaction_id: Optional[str] = None,
    status: Optional[PaymentStatus] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin)
):
    """
    Search payments with various filters (Admin only)
    """
    payments = search_payments(
        db=db,
        email=email,
        student_id=student_id,
        transaction_id=transaction_id,
        status=status
    )
    
    # Additional date filtering if provided
    if start_date or end_date:
        filtered_payments = []
        for payment in payments:
            if start_date and payment.created_at < start_date:
                continue
            if end_date and payment.created_at > end_date:
                continue
            filtered_payments.append(payment)
        payments = filtered_payments
    
    return payments

@router.put("/update/{payment_id}", response_model=PaymentInDB)
def update_payment(
    payment_id: int,
    payment_update: PaymentUpdate,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin)
):
    """
    Update payment details (Admin only)
    """
    payment = get_payment_by_id(db, payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Update fields
    if payment_update.status:
        payment.status = payment_update.status
        if payment_update.status == PaymentStatus.VERIFIED:
            payment.verified_by = admin.id
            payment.verified_at = datetime.now()
    
    if payment_update.transaction_id:
        payment.transaction_id = payment_update.transaction_id
    
    db.commit()
    db.refresh(payment)
    
    return payment

@router.get("/export")
def export_payments(
    format: str = Query("csv", pattern="^(csv|excel)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin)
):
    """
    Export payments data (Admin only)
    """
    import pandas as pd
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    
    # Get payments
    payments = search_payments(db)
    
    # Filter by date if provided
    if start_date or end_date:
        filtered = []
        for payment in payments:
            if start_date and payment.created_at < start_date:
                continue
            if end_date and payment.created_at > end_date:
                continue
            filtered.append(payment)
        payments = filtered
    
    # Prepare data for export
    data = []
    for payment in payments:
        participant = payment.participant
        user = participant.user if participant else None
        
        data.append({
            "Payment ID": payment.id,
            "Participant Name": user.full_name if user else "N/A",
            "Email": user.email if user else "N/A",
            "University": user.university if user else "N/A",
            "Track": participant.track.value if participant else "N/A",
            "Team": participant.team.name if participant and participant.team else "Individual",
            "Amount": payment.amount,
            "Payment Method": payment.payment_method.value,
            "Status": payment.status.value,
            "Transaction ID": payment.transaction_id,
            "Receipt Path": payment.receipt_path,
            "Verified By": payment.verified_by,
            "Verified At": payment.verified_at,
            "Created At": payment.created_at,
            "Updated At": payment.updated_at
        })
    
    df = pd.DataFrame(data)
    
    if format == "excel":
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Payments')
        output.seek(0)
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=devcon26_payments.xlsx"}
        )
    else:
        csv_data = df.to_csv(index=False)
        return StreamingResponse(
            iter([csv_data]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=devcon26_payments.csv"}
        )