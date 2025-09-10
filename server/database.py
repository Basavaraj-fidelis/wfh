from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import os

# Use SQLite for development if PostgreSQL is not available
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./monitoring.db")

# Handle PostgreSQL URL format for production
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://")

try:
    if DATABASE_URL.startswith("sqlite"):
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    print(f"Database connected successfully: {DATABASE_URL.split('@')[0] if '@' in DATABASE_URL else 'Local SQLite'}")
except Exception as e:
    print(f"Database connection error: {e}")
    # Fallback to SQLite
    DATABASE_URL = "sqlite:///./monitoring.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    print("Fallback: Using SQLite database")

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
    activity_data = Column(Text, default="{}")  # JSON string for comprehensive activity tracking
    timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

class EmployeeActivitySummary(Base):
    __tablename__ = "employee_activity_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    date = Column(String, index=True)  # YYYY-MM-DD format
    total_active_minutes = Column(Integer, default=0)
    total_tracked_minutes = Column(Integer, default=0)
    activity_rate_percentage = Column(Integer, default=0)
    productivity_score = Column(Integer, default=0)
    apps_used_count = Column(Integer, default=0)
    websites_visited_count = Column(Integer, default=0)
    screen_lock_count = Column(Integer, default=0)
    browser_events_count = Column(Integer, default=0)
    activitywatch_available = Column(Boolean, default=False)
    app_usage_data = Column(Text, default="{}")  # JSON string
    website_usage_data = Column(Text, default="{}")  # JSON string
    activitywatch_data = Column(Text, default="{}")  # JSON string
    network_location_data = Column(Text, default="{}")  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class EmployeeHourlyActivity(Base):
    __tablename__ = "employee_hourly_activity"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    date = Column(String, index=True)  # YYYY-MM-DD format
    hour = Column(Integer, index=True)  # 0-23
    active_minutes = Column(Integer, default=0)
    idle_minutes = Column(Integer, default=0)
    top_app = Column(String, default="")
    top_website = Column(String, default="")
    keyboard_mouse_events = Column(Integer, default=0)
    screen_locked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class EmployeeDetailedLog(Base):
    __tablename__ = "employee_detailed_logs"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    hostname = Column(String)
    local_ip = Column(String)
    public_ip = Column(String)
    location = Column(Text)  # JSON string
    screenshot_path = Column(String)
    activity_data = Column(Text, default="{}")  # JSON string for activity tracking
    timestamp = Column(DateTime, default=datetime.utcnow)

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