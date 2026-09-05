from sqlalchemy import Column, String, Boolean, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()

class License(Base):
    __tablename__ = 'licenses'
    
    # The actual license key string
    license_key = Column(String, primary_key=True, index=True)
    
    # The unique fingerprint of the device
    hardware_id = Column(String, nullable=True)
    
    is_active = Column(Boolean, default=True)
    expiration_date = Column(DateTime, nullable=False)

# Database connection setup
DATABASE_URL = "postgresql+psycopg2://neondb_owner:npg_KwvobQUX5dE6@ep-fragrant-sound-aeeotcg1-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)