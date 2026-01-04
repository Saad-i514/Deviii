import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
import os
import json
from datetime import datetime
from typing import Optional
from app.config import settings

def generate_qr_code(
    participant_id: int,
    user_name: str,
    email: str,
    track: str,
    team_name: Optional[str] = None
) -> str:
    """Generate QR code for participant entry"""
    
    # Create QR data
    qr_data = {
        "participant_id": participant_id,
        "name": user_name,
        "email": email,
        "track": track,
        "team": team_name,
        "event": "Devcon '26",
        "generated_at": datetime.now().isoformat(),
        "valid": True
    }
    
    # Convert to JSON string
    qr_content = json.dumps(qr_data)
    
    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    
    qr.add_data(qr_content)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR code
    filename = f"qr_{participant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    file_path = os.path.join(settings.QR_CODE_DIR, filename)
    
    img.save(file_path)
    
    return file_path

def verify_qr_code(qr_data_str: str) -> dict:
    """Verify QR code data"""
    try:
        qr_data = json.loads(qr_data_str)
        
        # Basic validation
        required_fields = ["participant_id", "name", "email", "track", "event"]
        if not all(field in qr_data for field in required_fields):
            return {"valid": False, "error": "Invalid QR code format"}
        
        if qr_data.get("event") != "Devcon '26":
            return {"valid": False, "error": "Invalid event"}
        
        if not qr_data.get("valid", False):
            return {"valid": False, "error": "QR code has been invalidated"}
        
        return {"valid": True, "data": qr_data}
        
    except json.JSONDecodeError:
        return {"valid": False, "error": "Invalid QR code data"}

def generate_team_qr_code(team_id: int, team_name: str, track: str, members: list) -> str:
    """Generate QR code for team entry"""
    
    qr_data = {
        "team_id": team_id,
        "team_name": team_name,
        "track": track,
        "members": [{"id": m["id"], "name": m["name"]} for m in members],
        "member_count": len(members),
        "event": "Devcon '26",
        "generated_at": datetime.now().isoformat(),
        "valid": True,
        "type": "team"
    }
    
    qr_content = json.dumps(qr_data)
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    
    qr.add_data(qr_content)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    filename = f"team_qr_{team_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    file_path = os.path.join(settings.QR_CODE_DIR, filename)
    
    img.save(file_path)
    
    return file_path