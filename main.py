from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from models import SessionLocal, License, engine

app = FastAPI(title="License Validation API")

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# JSON Payload structure expected from the client software
class ActivationRequest(BaseModel):
    license_key: str
    hardware_id: str

@app.post("/activate")
def activate_license(req: ActivationRequest, db: Session = Depends(get_db)):
    db_license = db.query(License).filter(License.license_key == req.license_key).first()
    
    if not db_license:
        raise HTTPException(status_code=404, detail="License key not found")
    if not db_license.is_active or db_license.expiration_date < datetime.utcnow():
        raise HTTPException(status_code=403, detail="License is inactive or expired")
        
    # Check if the key is already bound to a different machine
    if db_license.hardware_id and db_license.hardware_id != req.hardware_id:
        raise HTTPException(status_code=403, detail="License is already bound to another device")
        
    # Bind the hardware ID if it's the first activation
    if not db_license.hardware_id:
        db_license.hardware_id = req.hardware_id
        db.commit()
        return {"status": "success", "message": "License successfully bound to device"}
        
    return {"status": "success", "message": "License already bound to this device"}

@app.post("/validate")
def validate_license(req: ActivationRequest, db: Session = Depends(get_db)):
    # This endpoint is kept extremely lightweight for fast response times
    db_license = db.query(License).filter(
        License.license_key == req.license_key,
        License.hardware_id == req.hardware_id,
        License.is_active == True
    ).first()
    
    if not db_license or db_license.expiration_date < datetime.utcnow():
        raise HTTPException(status_code=403, detail="Validation failed")
        
    return {"status": "valid"}