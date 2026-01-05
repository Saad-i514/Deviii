from pydantic import BaseModel, field_validator, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum
from decimal import Decimal

class PaymentMethod(str, Enum):
    ONLINE = "online"
    CASH = "cash"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    PENDING_CASH = "pending_cash"

class PaymentBase(BaseModel):
    amount: float
    payment_method: PaymentMethod
    transaction_id: Optional[str] = None

class PaymentCreate(PaymentBase):
    
    receipt_path: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    
    # For team payments (if paying for entire team)
    pay_for_team: bool = False

class PaymentOnlineCreate(BaseModel):
    transaction_id: str
    bank_name: Optional[str] = None
    reference_number: Optional[str] = None
    payment_date: datetime
    
    @field_validator('payment_date')
    def validate_payment_date(cls, v):
        if v > datetime.now():
            raise ValueError('Payment date cannot be in the future')
        return v

class PaymentCashCreate(BaseModel):
    collected_by: str  # Ambassador name who collected cash
    collected_at: datetime
    
    @field_validator('collected_at')
    def validate_collected_at(cls, v):
        if v > datetime.now():
            raise ValueError('Collection date cannot be in the future')
        return v

class PaymentUpdate(BaseModel):
    status: Optional[PaymentStatus] = None
    transaction_id: Optional[str] = None
    remarks: Optional[str] = None
    
class PaymentVerification(BaseModel):
    participant_id: int
    amount_collected: float
    collected_at: datetime
    ambassador_notes: Optional[str] = None
    
class PaymentInDB(PaymentBase):
    id: int
    participant_id: int
    team_id: Optional[int]
    status: PaymentStatus
    receipt_path: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class PaymentSummary(BaseModel):
    total_participants: int
    paid_participants: int
    pending_payments: int
    total_collected: float
    expected_revenue: float
    track_breakdown: dict

class PaymentDashboard(BaseModel):
    summary: PaymentSummary
    recent_payments: List[PaymentInDB]
    pending_verifications: List[PaymentInDB]

class PaymentReceiptUpload(BaseModel):
    transaction_id: str
    payment_date: datetime
    amount: float
    bank_name: str
    
    @field_validator('amount')
    def validate_amount(cls, v):
        from app.config import settings
        if v < settings.REGISTRATION_FEE:
            raise ValueError(f'Amount must be at least {settings.REGISTRATION_FEE}')
        return v

# For admin/ambassador views
class PaymentWithParticipant(PaymentInDB):
    participant_name: Optional[str] = None
    participant_email: Optional[str] = None
    participant_university: Optional[str] = None
    track: Optional[str] = None
    team_name: Optional[str] = None

# For export
class PaymentExport(BaseModel):
    payment_id: int
    participant_name: str
    email: str
    university: str
    track: str
    team: Optional[str]
    amount: float
    payment_method: str
    status: str
    transaction_id: Optional[str]
    verified_by: Optional[str]
    verified_at: Optional[datetime]
    created_at: datetime