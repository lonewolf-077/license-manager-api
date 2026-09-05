import os
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import pyotp

from models import SessionLocal, License, init_db
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.on_event("startup")
def startup_event():
    init_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper function to enforce Admin Secret + MFA
def verify_admin_auth(x_admin_secret: str, x_admin_mfa: str):
    expected_secret = os.getenv("ADMIN_SECRET", "super-secret-default-key")
    totp_secret = os.getenv("ADMIN_TOTP_SECRET")

    if x_admin_secret != expected_secret:
        raise HTTPException(status_code=403, detail="Unauthorized: Invalid Admin Secret")

    if not totp_secret:
        raise HTTPException(status_code=500, detail="Server Error: ADMIN_TOTP_SECRET not configured")

    totp = pyotp.TOTP(totp_secret)
    # valid_window=1 allows a +/- 30s clock drift buffer
    if not totp.verify(x_admin_mfa.strip(), valid_window=1):
        raise HTTPException(status_code=403, detail="Unauthorized: Invalid or expired MFA code")

class ActivationRequest(BaseModel):
    key: str
    hardware_id: str

@app.post("/activate")
def activate_license(data: ActivationRequest, db: Session = Depends(get_db)):
    license_obj = db.query(License).filter(License.key == data.key).first()
    
    if not license_obj:
        raise HTTPException(status_code=404, detail="Invalid license key")
        
    if not license_obj.is_active:
        raise HTTPException(status_code=403, detail="License key has been deactivated")
        
    if license_obj.expiration_date and license_obj.expiration_date < datetime.utcnow():
        raise HTTPException(status_code=403, detail="License key has expired")
        
    if license_obj.hardware_id and license_obj.hardware_id != data.hardware_id:
        raise HTTPException(status_code=400, detail="License already bound to another device")
        
    if not license_obj.hardware_id:
        license_obj.hardware_id = data.hardware_id
        db.commit()
        
    return {"status": "success", "message": "License successfully bound to device"}

class KeyGenerationRequest(BaseModel):
    app_name: Optional[str] = "General App"
    user_name: str
    email: Optional[str] = None

@app.post("/admin/generate-key")
@limiter.limit("5/minute")
def create_license_key(
    request: Request, 
    data: KeyGenerationRequest, 
    x_admin_secret: str = Header(...),
    x_admin_mfa: str = Header(...),
    db: Session = Depends(get_db)
):
    verify_admin_auth(x_admin_secret, x_admin_mfa)
    
    if not data.user_name or not data.user_name.strip():
        raise HTTPException(status_code=400, detail="user_name is required")
    
    raw_id = uuid.uuid4().hex.upper()
    formatted_key = f"{raw_id[:4]}-{raw_id[4:8]}-{raw_id[8:12]}-{raw_id[12:16]}"
    
    new_license = License(
        key=formatted_key,
        hardware_id=None,
        app_name=data.app_name,
        user_name=data.user_name.strip(),
        email=data.email
    )
    
    db.add(new_license)
    db.commit()
    
    return {
        "status": "success",
        "key": formatted_key,
        "app_name": data.app_name,
        "user_name": data.user_name,
        "email": data.email,
        "created_at": datetime.utcnow().isoformat()
    }

@app.get("/admin/keys")
@limiter.limit("10/minute")
def get_all_licenses(
    request: Request, 
    x_admin_secret: str = Header(...), 
    x_admin_mfa: str = Header(...),
    db: Session = Depends(get_db)
):
    verify_admin_auth(x_admin_secret, x_admin_mfa)
    
    licenses = db.query(License).all()
    total_keys = len(licenses)
    assigned_keys = sum(1 for l in licenses if l.hardware_id)
    unassigned_keys = total_keys - assigned_keys
    
    return {
        "stats": {
            "total": total_keys,
            "assigned": assigned_keys,
            "unassigned": unassigned_keys
        },
        "licenses": [
            {
                "id": l.id,
                "key": l.key,
                "app_name": getattr(l, "app_name", "N/A"),
                "user_name": getattr(l, "user_name", "N/A"),
                "email": getattr(l, "email", "N/A"),
                "hardware_id": l.hardware_id if l.hardware_id else "Unassigned",
                "is_active": l.is_active,
                "expiration_date": l.expiration_date.isoformat() if l.expiration_date else "Never"
            }
            for l in licenses
        ]
    }