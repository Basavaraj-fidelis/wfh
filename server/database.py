from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/defaultdb")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class EmployeeHeartbeat(Base):
    __tablename__ = "employee_heartbeats"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    hostname = Column(String)
    status = Column(String, default="online")
    timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

class EmployeeLog(Base):
    __tablename__ = "employee_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    hostname = Column(String)
    local_ip = Column(String)
    public_ip = Column(String)
    location = Column(Text)  # JSON string with location data
    screenshot_path = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

class AdminUser(Base):
    __tablename__ = "admin_users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create tables
def create_tables():
    Base.metadata.create_all(bind=engine)