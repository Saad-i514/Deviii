from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.security import decode_token
from app.crud.user import get_user_by_email
from app.schemas.user import TokenData, UserRole
from app.crud.participant import get_participant_by_user_id

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),db: Session = Depends(get_db)):
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid authentication credentials",headers={"WWW-Authenticate": "Bearer"},
        )
    
    email: str = payload.get("sub")
    if email is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid authentication credentials")
    
    user = get_user_by_email(db, email=email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="User not found",
        )
    
    return user

def get_current_participant(user = Depends(get_current_user),db: Session = Depends(get_db)):
     
    # Allow participants, admins, ambassadors, and registration team to access participant endpoints
    allowed_roles = [UserRole.PARTICIPANT, UserRole.ADMIN, UserRole.AMBASSADOR, UserRole.REGISTRATION_TEAM]
    if user.role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Access denied"
        )
    
    participant = get_participant_by_user_id(db, user.id)
    if not participant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Participant profile not found")
    
    return participant

def require_role(required_role: UserRole):
    def role_checker(current_user = Depends(get_current_user)):
        # Allow admins to access everything, and allow multi-role access
        allowed_roles = [required_role, UserRole.ADMIN]
        
        # Special cases for multi-role access
        if required_role == UserRole.AMBASSADOR:
            allowed_roles.extend([UserRole.PARTICIPANT, UserRole.REGISTRATION_TEAM])
        elif required_role == UserRole.REGISTRATION_TEAM:
            allowed_roles.extend([UserRole.PARTICIPANT, UserRole.AMBASSADOR])
            
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail=f"Requires {required_role} role or compatible role"
            )
        return current_user
    return role_checker

# Role-specific dependencies
get_current_admin = require_role(UserRole.ADMIN)
get_current_ambassador = require_role(UserRole.AMBASSADOR)
get_current_registration_team = require_role(UserRole.REGISTRATION_TEAM)