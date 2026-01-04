from fastapi import HTTPException, UploadFile
from typing import List
import re
import os

def validate_file_upload(
    file: UploadFile, 
    allowed_extensions: List[str], 
    max_size: int
) -> None:
    """Validate uploaded file"""
    
    # Check file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {max_size / (1024*1024):.1f}MB"
        )

def validate_cnic(cnic: str) -> bool:
    """Validate Pakistani CNIC format"""
    pattern = r'^\d{5}-\d{7}-\d{1}$'
    return bool(re.match(pattern, cnic))

def validate_student_id(student_id: str) -> bool:
    """Validate student ID format"""
    # Basic validation - adjust based on your requirements
    return len(student_id) >= 4 and student_id.isalnum()

def validate_phone_number(phone: str) -> bool:
    """Validate Pakistani phone number"""
    # Remove spaces and dashes
    phone = re.sub(r'[\s-]', '', phone)
    
    # Pakistani mobile patterns
    patterns = [
        r'^(\+92|0092|92)?3\d{9}$',  # Mobile
        r'^(\+92|0092|92)?\d{2,3}\d{7,8}$'  # Landline
    ]
    
    return any(re.match(pattern, phone) for pattern in patterns)

def validate_team_name(name: str) -> bool:
    """Validate team name"""
    if len(name) < 3 or len(name) > 50:
        return False
    
    # Allow alphanumeric, spaces, and some special characters
    pattern = r'^[a-zA-Z0-9\s\-_\.]+$'
    return bool(re.match(pattern, name))

def validate_github_url(url: str) -> bool:
    """Validate GitHub URL"""
    if not url:
        return True  # Optional field
    
    pattern = r'^https?://github\.com/[\w\-\.]+/?$'
    return bool(re.match(pattern, url))

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove path separators and dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = re.sub(r'\.\.', '_', filename)
    return filename[:100]  # Limit length