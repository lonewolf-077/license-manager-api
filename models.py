import os
from sqlalchemy import Column, String, Boolean, DateTime, Integer, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timedelta

Base = declarative_base()

class License(Base):
    __tablename__ = "licenses"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    hardware_id = Column(String, nullable=True)
    
    # New Client Metadata Columns
    app_name = Column(String, nullable=True)
    user_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    
    is_active = Column(Boolean, default=True)
    expiration_date = Column(DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(days=365))

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set!")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)