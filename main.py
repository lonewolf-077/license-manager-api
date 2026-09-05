import os
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, Request, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Import your models and database tools
from models import SessionLocal, License, init_db

# Import slowapi rate-limiting tools
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

app = FastAPI()

# Initialize the rate limiter (tracks requests by IP address)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Automatically create database tables when the app starts up on Render
@app.on_event("startup")
def startup_event():
    init_db()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ActivationRequest(BaseModel):
    key: str
    hardware_id: str

# 1. CLIENT ENDPOINT
@app.post("/activate")
def activate_license(data: ActivationRequest, db: Session = Depends(get_db)):
    license_obj = db.query(License).filter(License.key == data.key).first()
    
    if not license_obj:
        raise HTTPException(status_code=404, detail="Invalid license key")
        
    if license_obj.hardware_id and license_obj.hardware_id != data.hardware_id:
        raise HTTPException(status_code=400, detail="License already bound to another device")
        
    if not license_obj.hardware_id:
        license_obj.hardware_id = data.hardware_id
        db.commit()
        
    return {"status": "success", "message": "License successfully bound to device"}

# 2. ADMIN ENDPOINT (Protected with Rate Limiting & Admin Secret Header)
@app.post("/admin/generate-key")
@limiter.limit("5/minute")
def create_license_key(
    request: Request, 
    x_admin_secret: str = Header(...), 
    db: Session = Depends(get_db)
):
    expected_secret = os.getenv("ADMIN_SECRET", "super-secret-default-key")
    
    if x_admin_secret != expected_secret:
        raise HTTPException(status_code=403, detail="Unauthorized: Invalid Admin Secret")
    
    raw_id = uuid.uuid4().hex.upper()
    formatted_key = f"{raw_id[:4]}-{raw_id[4:8]}-{raw_id[8:12]}-{raw_id[12:16]}"
    
    new_license = License(
        key=formatted_key,
        hardware_id=None
    )
    
    db.add(new_license)
    db.commit()
    
    return {
        "status": "success",
        "key": formatted_key,
        "created_at": datetime.utcnow().isoformat()
    }