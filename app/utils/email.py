import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from typing import List, Optional
from app.config import settings

class EmailService:
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.username = settings.SMTP_USERNAME
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.FROM_EMAIL

    async def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        attachments: Optional[List[str]] = None
    ):
        """Send email with optional attachments"""
        
        msg = MIMEMultipart()
        msg['From'] = self.from_email
        msg['To'] = ', '.join(to_emails)
        msg['Subject'] = subject

        # Add text body
        text_part = MIMEText(body, 'plain')
        msg.attach(text_part)

        # Add attachments if provided
        if attachments:
            for file_path in attachments:
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {os.path.basename(file_path)}'
                        )
                        msg.attach(part)

        # Send email
        try:
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_server,
                port=self.smtp_port,
                start_tls=True,
                username=self.username,
                password=self.password
            )
            return True
        except Exception as e:
            print(f"Email sending failed: {e}")
            return False

    async def send_registration_pending_email(self, user_name: str, email: str, track: str):
        """Send registration pending email"""
        subject = "[SYSTEM_LOG]: Registration Initiated for Devcon '26"
        
        body = f"""Hello {user_name},

Registration initiated for {track.upper()} track at Devcon '26.

To finalize your slot, please complete your payment via:
- Online portal (upload payment receipt)
- Visit a Devcon Ambassador on campus for cash payment

Status: PENDING_PAYMENT

Next Steps:
1. Complete payment process
2. Await verification
3. Receive your QR entry ticket

---
Devcon '26 Registration System"""

        return await self.send_email([email], subject, body)

    async def send_payment_verified_email(
        self, 
        user_name: str, 
        email: str, 
        track: str,
        qr_code_path: Optional[str] = None
    ):
        """Send payment verified email with QR code"""
        subject = "[CLEARANCE_GRANTED]: Welcome to Devcon '26, " + user_name
        
        body = f"""Hello {user_name},

Your payment has been verified. You are now officially registered for Devcon '26.

Event Details:
- Track: {track.upper()}
- Status: VERIFIED

Your unique QR Code Ticket is attached for entry to:
- Opening Ceremony at SH-1
- Social Night: Mehfil-e-Samaa
- All track events

Important:
- Keep your QR code safe
- Present at entry points
- Backup: Save to phone gallery

See you at Devcon '26!

---
Devcon '26 Registration System"""

        attachments = [qr_code_path] if qr_code_path and os.path.exists(qr_code_path) else None
        return await self.send_email([email], subject, body, attachments)

    async def send_payment_rejected_email(self, user_name: str, email: str, reason: str = ""):
        """Send payment rejection email"""
        subject = "[SYSTEM_ALERT]: Payment Verification Failed"
        
        body = f"""Hello {user_name},

Your payment could not be verified.

Reason: {reason if reason else "Invalid or unclear payment proof"}

Next Steps:
1. Check your payment receipt
2. Re-upload clear payment proof
3. Contact support if payment was successful
4. Alternative: Visit campus ambassador for cash payment

Status: PAYMENT_REJECTED
Action Required: RE_SUBMIT_PAYMENT_PROOF

---
Devcon '26 Registration System"""

        return await self.send_email([email], subject, body)

    async def send_team_invitation_email(
        self, 
        invitee_name: str, 
        invitee_email: str, 
        team_name: str, 
        team_code: str,
        inviter_name: str
    ):
        """Send team invitation email"""
        subject = f"Team Invitation: Join {team_name} at Devcon '26"
        
        body = f"""Hello {invitee_name},

{inviter_name} has invited you to join team "{team_name}" for Devcon '26.

Team Code: {team_code}

To join:
1. Register at Devcon '26 portal
2. Enter team code: {team_code}
3. Complete your registration

---
Devcon '26 Registration System"""

        return await self.send_email([invitee_email], subject, body)

# Create global email service instance
email_service = EmailService()