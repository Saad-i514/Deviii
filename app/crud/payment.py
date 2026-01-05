from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timedelta
import os

from app.models.payment import Payment, PaymentStatus, PaymentMethod
from app.models.participant import Participant
from app.models.user import User
from app.models.team import Team
from app.schemas.payment import (PaymentCreate, PaymentOnlineCreate, PaymentCashCreate,PaymentUpdate,PaymentStatus
)
from app.config import settings

def create_payment(db: Session, participant_id: int,team_id: Optional[int],amount: float,payment_method: PaymentMethod,transaction_id: Optional[str] = None,receipt_path: Optional[str] = None) -> Payment:
    """Create a new payment record"""
    
    # Set initial status based on payment method
    if payment_method == PaymentMethod.ONLINE:
        status = PaymentStatus.PENDING
    else:
        status = PaymentStatus.PENDING_CASH
    
    db_payment = Payment(
        participant_id=participant_id,
        team_id=team_id,
        amount=amount,
        payment_method=payment_method,
        status=status,
        transaction_id=transaction_id,
        receipt_path=receipt_path,
        uploaded_at=datetime.now() if receipt_path else None
    )
    
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment

def get_payment_by_id(db: Session, payment_id: int) -> Optional[Payment]:
    """Get payment by ID"""
    return db.query(Payment).filter(Payment.id == payment_id).first()

def get_payment_by_participant(db: Session, participant_id: int) -> Optional[Payment]:
    """Get payment for a specific participant"""
    return db.query(Payment).filter(Payment.participant_id == participant_id).first()

def get_payments_by_team(db: Session, team_id: int) -> List[Payment]:
    """Get all payments for a team"""
    return db.query(Payment).filter(Payment.team_id == team_id).all()

def update_payment_status(db: Session, payment_id: int, status: PaymentStatus,verified_by: Optional[int] = None
) -> Optional[Payment]:
    """Update payment status"""
    payment = get_payment_by_id(db, payment_id)
    if payment:
        payment.status = status
        if status == PaymentStatus.VERIFIED and verified_by:
            payment.verified_by = verified_by
            payment.verified_at = datetime.now()
        db.commit()
        db.refresh(payment)
    return payment

def verify_cash_payment(db: Session,participant_id: int,ambassador_id: int
) -> Optional[Payment]:
    """Verify a cash payment (for ambassadors)"""
    payment = get_payment_by_participant(db, participant_id)
    if payment and payment.payment_method == PaymentMethod.CASH:
        payment.status = PaymentStatus.VERIFIED
        payment.verified_by = ambassador_id
        payment.verified_at = datetime.now()
        db.commit()
        db.refresh(payment)
    return payment

def verify_online_payment(db: Session,payment_id: int,approve: bool = True,admin_id: Optional[int] = None
) -> Optional[Payment]:
    """Verify or reject an online payment (for admins)"""
    payment = get_payment_by_id(db, payment_id)
    if payment and payment.payment_method == PaymentMethod.ONLINE:
        if approve:
            payment.status = PaymentStatus.VERIFIED
            payment.verified_by = admin_id
            payment.verified_at = datetime.now()
        else:
            payment.status = PaymentStatus.REJECTED
        db.commit()
        db.refresh(payment)
    return payment

def get_payments_summary(db: Session) -> Dict:
    """Get comprehensive payment summary"""
    
    # Get total counts
    total_participants = db.query(Participant).count()
    
    # Get payment counts by status
    payment_stats = db.query(
        Payment.status,
        func.count(Payment.id).label('count'),
        func.coalesce(func.sum(Payment.amount), 0).label('total')
    ).group_by(Payment.status).all()
    
    # Convert to dictionary
    stats_dict = {
        'total_participants': total_participants,
        'total_collected': 0,
        'expected_revenue': total_participants * settings.REGISTRATION_FEE,
        'by_status': {},
        'by_method': {}
    }
    
    for status, count, total in payment_stats:
        stats_dict['by_status'][status] = {
            'count': count,
            'total': float(total)
        }
        if status == PaymentStatus.VERIFIED:
            stats_dict['total_collected'] += float(total)
    
    # Get counts by payment method
    method_stats = db.query(
        Payment.payment_method,
        func.count(Payment.id).label('count')
    ).group_by(Payment.payment_method).all()
    
    for method, count in method_stats:
        stats_dict['by_method'][method] = count
    
    return stats_dict

def get_pending_verifications(db: Session) -> List[Payment]:
    """Get all payments pending verification"""
    return db.query(Payment).filter(
        or_(
            Payment.status == PaymentStatus.PENDING,
            Payment.status == PaymentStatus.PENDING_CASH
        )
    ).options(
        joinedload(Payment.participant).joinedload(Participant.user)
    ).all()

def get_recent_payments(
    db: Session, 
    limit: int = 20
) -> List[Payment]:
    """Get recent payments with participant info"""
    return db.query(Payment).join(Participant).join(User).filter(
        Payment.status == PaymentStatus.VERIFIED
    ).order_by(
        Payment.verified_at.desc()
    ).limit(limit).all()

def search_payments(
    db: Session,
    email: Optional[str] = None,
    student_id: Optional[str] = None,
    transaction_id: Optional[str] = None,
    status: Optional[PaymentStatus] = None
) -> List[Payment]:
    """Search payments by various criteria"""
    query = db.query(Payment).join(Participant).join(User)
    
    if email:
        query = query.filter(User.email.ilike(f"%{email}%"))
    if student_id:
        query = query.filter(Participant.student_id.ilike(f"%{student_id}%"))
    if transaction_id:
        query = query.filter(Payment.transaction_id.ilike(f"%{transaction_id}%"))
    if status:
        query = query.filter(Payment.status == status)
    
    return query.options(
        joinedload(Payment.participant).joinedload(Participant.user),
        joinedload(Payment.team)
    ).all()

def delete_payment(db: Session, payment_id: int) -> bool:
    """Delete a payment record"""
    payment = get_payment_by_id(db, payment_id)
    if payment:
        # Delete receipt file if exists
        if payment.receipt_path and os.path.exists(payment.receipt_path):
            try:
                os.remove(payment.receipt_path)
            except:
                pass  # Don't fail if file deletion fails
        
        db.delete(payment)
        db.commit()
        return True
    return False

def get_payments_by_date_range(
    db: Session,
    start_date: datetime,
    end_date: datetime
) -> List[Payment]:
    """Get payments within a date range"""
    return db.query(Payment).filter(
        and_(
            Payment.created_at >= start_date,
            Payment.created_at <= end_date
        )
    ).options(
        joinedload(Payment.participant).joinedload(Participant.user)
    ).all()

def get_team_payment_status(db: Session, team_id: int) -> Dict:
    """Get payment status for all team members"""
    payments = get_payments_by_team(db, team_id)
    
    status = {
        'team_id': team_id,
        'total_members': 0,
        'paid_members': 0,
        'pending_members': 0,
        'total_collected': 0,
        'members': []
    }
    
    # Get team members
    team = db.query(Team).filter(Team.id == team_id).first()
    if team:
        status['total_members'] = len(team.members)
        
        for member in team.members:
            member_status = {
                'id': member.id,
                'name': member.user.full_name,
                'payment_status': 'unpaid'
            }
            
            # Find payment for this member
            payment = next((p for p in payments if p.participant_id == member.id), None)
            if payment:
                member_status['payment_status'] = payment.status.value
                member_status['payment_id'] = payment.id
                member_status['amount'] = payment.amount
                member_status['method'] = payment.payment_method.value
                
                if payment.status == PaymentStatus.VERIFIED:
                    status['paid_members'] += 1
                    status['total_collected'] += payment.amount
                else:
                    status['pending_members'] += 1
            else:
                status['pending_members'] += 1
            
            status['members'].append(member_status)
    
    return status

def update_payment_receipt(
    db: Session,
    payment_id: int,
    receipt_path: str
) -> Optional[Payment]:
    """Update payment receipt path"""
    payment = get_payment_by_id(db, payment_id)
    if payment:
        # Delete old receipt if exists
        if payment.receipt_path and os.path.exists(payment.receipt_path):
            try:
                os.remove(payment.receipt_path)
            except:
                pass
        
        payment.receipt_path = receipt_path
        payment.uploaded_at = datetime.now()
        db.commit()
        db.refresh(payment)
    return payment