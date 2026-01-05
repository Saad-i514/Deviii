# 🚀 Devcon '26 API Guide

## Base URL: `http://127.0.0.1:8000`

---

## 🔐 Authentication

### Register User
```bash
POST /api/v1/auth/register
{
  "email": "user@example.com",
  "password": "password123",
  "full_name": "User Name",
  "university": "University Name", 
  "phone_number": "+923001234567",
  "role": "participant|admin|ambassador|registration_team"
}
```

### Login
```bash
POST /api/v1/auth/login
username=user@example.com&password=password123
```
**Returns:** `{"access_token": "...", "token_type": "bearer", "role": "..."}`

### Get Current User
```bash
GET /api/v1/auth/me
Authorization: Bearer <token>
```

---

## 🌐 Public Endpoints (No Auth Required)

### Get Tracks
```bash
GET /api/v1/public/tracks
```
**Returns:** Available competition tracks (programming, ideathon, etc.)

### Get Universities
```bash
GET /api/v1/public/universities
```
**Returns:** List of supported universities

### Get Statistics
```bash
GET /api/v1/public/stats
```
**Returns:** Registration and payment statistics

### Public Registration
```bash
POST /api/v1/public/register
{
  "email": "student@university.edu",
  "password": "password123",
  "full_name": "Student Name",
  "university": "University Name",
  "phone_number": "+923001234567",
  "student_id": "2024-CS-001",
  "cnic": "12345-1234567-1",
  "track": "programming",
  "tshirt_size": "M",
  "emergency_contact": "+923009876543",
  "create_new_team": true,
  "team_name": "Team Name"
}
```

### Select Payment Method
```bash
POST /api/v1/public/select-payment-method
{
  "email": "student@university.edu",
  "payment_method": "online|cash"
}
```

### Upload Payment Receipt
```bash
POST /api/v1/public/upload-payment-receipt
Form Data:
- email: student@university.edu
- transaction_id: TXN123456789
- receipt: <file>
```

### Check Registration Status
```bash
POST /api/v1/public/check-status
{
  "email": "student@university.edu"
}
```

---

## 🎓 Participant Endpoints (Requires Participant Token)

### Select Cash Payment
```bash
POST /api/v1/payments/select-cash
Authorization: Bearer <participant_token>
```

### Get My Payment Status
```bash
GET /api/v1/payments/my-payment
Authorization: Bearer <participant_token>
```

### Get Team Payment Status
```bash
GET /api/v1/payments/team-payment-status/{team_id}
Authorization: Bearer <participant_token>
```

---

## 🏛️ Ambassador Endpoints (Requires Ambassador Token)

### Search Participants
```bash
POST /api/v1/ambassador/search
Authorization: Bearer <ambassador_token>
{
  "email": "student@university.edu"
}
```

### Get Participant Details
```bash
GET /api/v1/ambassador/participant/{participant_id}
Authorization: Bearer <ambassador_token>
```

### Verify Cash Payment
```bash
POST /api/v1/ambassador/verify-cash
Authorization: Bearer <ambassador_token>
{
  "participant_id": 123,
  "amount_collected": 500.0,
  "collected_at": "2024-01-05T10:30:00Z",
  "ambassador_notes": "Payment collected on campus"
}
```

### Get Pending Cash Payments
```bash
GET /api/v1/ambassador/pending-cash
Authorization: Bearer <ambassador_token>
```

### Get Ambassador Statistics
```bash
GET /api/v1/ambassador/stats
Authorization: Bearer <ambassador_token>
```

---

## 👨‍💼 Admin Endpoints (Requires Admin Token)

### Admin Dashboard
```bash
GET /api/v1/admin/dashboard
Authorization: Bearer <admin_token>
```
**Returns:** Total registrations, payments, track breakdown

### Get All Participants
```bash
GET /api/v1/admin/participants?skip=0&limit=100&track=programming
Authorization: Bearer <admin_token>
```

### Verify Online Payment
```bash
POST /api/v1/admin/verify-online/{payment_id}?approve=true&remarks=Verified
Authorization: Bearer <admin_token>
```
**Effect:** Approves payment, sends email with QR code

### Create Admin User
```bash
POST /api/v1/admin/create-user
Authorization: Bearer <admin_token>
{
  "email": "newadmin@example.com",
  "password": "password123",
  "full_name": "New Admin",
  "role": "admin|ambassador|registration_team"
}
```

### Update User Role
```bash
PUT /api/v1/admin/update-user-role
Authorization: Bearer <admin_token>
{
  "user_id": 123,
  "role": "ambassador"
}
```

### Export Participants
```bash
GET /api/v1/admin/export/participants?format=csv
Authorization: Bearer <admin_token>
```

### Check-in Participant
```bash
POST /api/v1/admin/check-in
Authorization: Bearer <admin_token>
{
  "qr_data": "encrypted_qr_string",
  "event_type": "opening_ceremony"
}
```

### Multi-Role Management
```bash
# Create participant profile for admin
POST /api/v1/admin/create-participant-profile
Authorization: Bearer <admin_token>
{participant_data}

# Grant ambassador access
POST /api/v1/admin/create-ambassador-profile
Authorization: Bearer <admin_token>
"user@example.com"

# Grant registration team access  
POST /api/v1/admin/create-registration-team-profile
Authorization: Bearer <admin_token>
"user@example.com"
```

---

## 🏢 Registration Team Endpoints (Requires Registration Team Token)

### Manual Cash Registration
```bash
POST /api/v1/registration-team/register-cash
Authorization: Bearer <team_token>
{
  "participant_id": 123,
  "amount": 500.0
}
```

---

## 🔄 Complete User Flows

### Participant Registration Flow
1. `POST /api/v1/public/register` - Register with details
2. `POST /api/v1/public/select-payment-method` - Choose online/cash
3. `POST /api/v1/public/upload-payment-receipt` - Upload receipt (if online)
4. Wait for admin/ambassador verification
5. Receive QR code via email

### Admin Payment Verification Flow
1. `POST /api/v1/auth/login` - Login as admin
2. `GET /api/v1/admin/participants` - View pending payments
3. `POST /api/v1/admin/verify-online/{id}?approve=true` - Approve payment
4. System sends QR code to participant

### Ambassador Cash Collection Flow
1. `POST /api/v1/auth/login` - Login as ambassador
2. `POST /api/v1/ambassador/search` - Find participant
3. Collect cash payment physically
4. `POST /api/v1/ambassador/verify-cash` - Mark as verified
5. System sends QR code to participant

---

## 🎯 Multi-Role Access

**Role Capabilities:**
- **Participant**: Registration, payment, team management
- **Ambassador**: Cash verification + participant features
- **Registration Team**: Manual registration + participant features  
- **Admin**: Full system access + all role features

**Cross-Role Access:**
- Admins can access ALL endpoints
- Ambassadors can access participant endpoints
- Registration team can access participant endpoints
- Users can have multiple role capabilities

---

## 📊 Payment Status Flow

```
Registration → Payment Selection → Processing → Verification → QR Code
```

**Online Payment:**
`pending` → `verified` (admin approval) → QR code sent

**Cash Payment:**
`pending_cash` → `verified` (ambassador collection) → QR code sent

---

## 🔧 Testing

Run comprehensive tests:
```bash
python comprehensive_test.py
```

**Test Coverage:**
- All endpoints with real email IDs
- Complete payment flows (online + cash)
- Multi-role access verification
- Email notification testing
- QR code generation

---

## 📧 Email Notifications

**Automatic emails sent for:**
- Registration confirmation
- Payment verification (approval/rejection)
- QR code delivery
- Team invitations

**Gmail Configuration Required:**
- SMTP settings in `config.py`
- Valid Gmail App Password
- Matching FROM_EMAIL and SMTP_USERNAME

---

## 🚨 Error Codes

- **200/201**: Success
- **400**: Bad request/validation error
- **401**: Authentication required
- **403**: Insufficient permissions
- **404**: Resource not found
- **422**: Data validation failed
- **500**: Server error

---

**API Documentation:** [http://127.0.0.1:8000/docs](https://web-production-5aa2b.up.railway.app/docs#/)
