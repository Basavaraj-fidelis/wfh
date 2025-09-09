import os
import json
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_
from pydantic import BaseModel

from database import get_db, create_tables, EmployeeHeartbeat, EmployeeLog, AdminUser
from auth import verify_admin_token, verify_agent_token, get_password_hash, create_access_token, verify_password

# Initialize database using lifespan context manager
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        print("Starting up application...")
        create_tables()
        print("Database tables created successfully")

        # Create default admin user if none exists
        db = next(get_db())
        admin = db.query(AdminUser).filter(AdminUser.username == "admin").first()
        if not admin:
            print("Creating default admin user...")
            hashed_password = get_password_hash("admin123")
            admin_user = AdminUser(username="admin", hashed_password=hashed_password)
            db.add(admin_user)
            db.commit()
            print("Default admin user created: admin/admin123")
        else:
            print("Admin user already exists")
        db.close()
        print("Application startup completed successfully")
    except Exception as e:
        print(f"Startup error: {e}")
        import traceback
        traceback.print_exc()

    yield

    # Shutdown (if needed)
    print("Application shutting down...")

# Create FastAPI app with lifespan
app = FastAPI(title="WFH Employee Monitoring System", version="1.0.0", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create uploads directory for screenshots
screenshots_dir = "screenshots"
os.makedirs(screenshots_dir, exist_ok=True)

# Serve static files from React build
try:
    app.mount("/assets", StaticFiles(directory="../frontend/dist/assets"), name="assets")
    app.mount("/static", StaticFiles(directory="../frontend/dist"), name="static")
except Exception as e:
    print(f"Warning: Could not mount static files: {e}")

# Pydantic models
class HeartbeatData(BaseModel):
    username: str
    hostname: str
    status: str = "online"

class DetailedLogData(BaseModel):
    username: str
    hostname: str
    local_ip: str
    public_ip: str
    location: str
    activity_data: str = "{}"

class AdminLogin(BaseModel):
    username: str
    password: str

class WorkingHoursResponse(BaseModel):
    username: str
    date: str
    total_hours: float
    first_seen: datetime
    last_seen: datetime

# Agent endpoints
@app.post("/api/heartbeat")
def receive_heartbeat(
    heartbeat: HeartbeatData,
    agent_auth=Depends(verify_agent_token),
    db: Session = Depends(get_db)
):
    """Receive heartbeat from agent"""
    heartbeat_record = EmployeeHeartbeat(
        username=heartbeat.username,
        hostname=heartbeat.hostname,
        status=heartbeat.status,
        timestamp=datetime.utcnow()
    )
    db.add(heartbeat_record)
    db.commit()
    return {"status": "success", "message": "Heartbeat received"}

@app.post("/api/log")
def receive_detailed_log(
    username: str = Form(...),
    hostname: str = Form(...),
    local_ip: str = Form(...),
    public_ip: str = Form(...),
    location: str = Form(...),
    activity_data: str = Form(default="{}"),
    screenshot: UploadFile = File(...),
    agent_auth=Depends(verify_agent_token),
    db: Session = Depends(get_db)
):
    """Receive detailed log with screenshot from agent"""
    try:
        print(f"Received detailed log from {username}@{hostname}")
        print(f"IPs: local={local_ip}, public={public_ip}")
        print(f"Location: {location}")
        print(f"Activity Data: {activity_data}")

        # Save screenshot
        timestamp = datetime.utcnow()
        filename = f"{username}_{timestamp.strftime('%Y%m%d_%H%M%S')}.png"
        screenshot_path = os.path.join(screenshots_dir, filename)

        print(f"Saving screenshot to: {screenshot_path}")

        with open(screenshot_path, "wb") as buffer:
            content = screenshot.file.read()
            buffer.write(content)
            print(f"Screenshot saved, size: {len(content)} bytes")

        # Save detailed log
        log_record = EmployeeLog(
            username=username,
            hostname=hostname,
            local_ip=local_ip,
            public_ip=public_ip,
            location=location,
            screenshot_path=screenshot_path,
            timestamp=timestamp,
            activity_data=activity_data
        )

        print(f"Saving log record to database...")
        db.add(log_record)
        db.commit()
        print(f"Log record saved successfully with ID: {log_record.id}")

        return {
            "status": "success",
            "message": "Detailed log received",
            "screenshot_saved": filename,
            "log_id": log_record.id
        }

    except Exception as e:
        print(f"Error processing detailed log: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to process log: {str(e)}")

# Admin authentication
@app.post("/api/admin/login")
def admin_login(login_data: AdminLogin, db: Session = Depends(get_db)):
    """Admin login endpoint"""
    try:
        print(f"Login attempt for username: {login_data.username}")
        admin = db.query(AdminUser).filter(AdminUser.username == login_data.username).first()

        if not admin:
            print(f"Admin user not found: {login_data.username}")
            raise HTTPException(status_code=401, detail="Incorrect username or password")

        if not verify_password(login_data.password, admin.hashed_password):
            print(f"Password verification failed for: {login_data.username}")
            raise HTTPException(status_code=401, detail="Incorrect username or password")

        print(f"Login successful for: {login_data.username}")
        access_token = create_access_token(data={"sub": admin.username})
        return {"access_token": access_token, "token_type": "bearer"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Test endpoint for location services
@app.get("/api/test/location/{ip}")
def test_location_service(ip: str):
    """Test location lookup service"""
    import requests
    try:
        response = requests.get(f'https://ipinfo.io/{ip}/json', timeout=10)
        if response.status_code == 200:
            return {"status": "success", "data": response.json()}
        else:
            return {"status": "error", "code": response.status_code, "text": response.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Debug endpoint to check admin user and database
@app.get("/api/debug/admin")
def debug_admin_user(db: Session = Depends(get_db)):
    """Debug endpoint to check admin user existence"""
    try:
        admin_count = db.query(AdminUser).count()
        admin = db.query(AdminUser).filter(AdminUser.username == "admin").first()

        return {
            "total_admin_users": admin_count,
            "admin_user_exists": admin is not None,
            "admin_username": admin.username if admin else None,
            "admin_is_active": admin.is_active if admin else None,
            "database_connected": True
        }
    except Exception as e:
        return {
            "error": str(e),
            "database_connected": False
        }

# Admin dashboard endpoints  
@app.get("/api/admin/employees/enhanced")
def get_enhanced_employee_data(admin=Depends(verify_admin_token), db: Session = Depends(get_db)):
    """Get enhanced employee data with working hours and productivity for today"""
    today = datetime.utcnow().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = start_of_day + timedelta(days=1)
    
    # Get all employees who have any activity
    all_employees = db.query(EmployeeHeartbeat.username).distinct().all()
    
    enhanced_data = []
    employee_id = 1
    
    for (username,) in all_employees:
        # Get today's heartbeats
        heartbeats = db.query(EmployeeHeartbeat).filter(
            EmployeeHeartbeat.username == username,
            EmployeeHeartbeat.timestamp >= start_of_day,
            EmployeeHeartbeat.timestamp < end_of_day
        ).order_by(EmployeeHeartbeat.timestamp).all()
        
        # Get latest heartbeat for status
        latest_heartbeat = db.query(EmployeeHeartbeat).filter(
            EmployeeHeartbeat.username == username
        ).order_by(desc(EmployeeHeartbeat.timestamp)).first()
        
        # Get latest log for location
        latest_log = db.query(EmployeeLog).filter(
            EmployeeLog.username == username
        ).order_by(desc(EmployeeLog.timestamp)).first()
        
        # Determine status
        cutoff_time = datetime.utcnow() - timedelta(minutes=10)
        status = "online" if latest_heartbeat and latest_heartbeat.timestamp > cutoff_time else "offline"
        
        # Calculate working hours and times
        if heartbeats:
            first_activity = heartbeats[0].timestamp
            last_activity = heartbeats[-1].timestamp
            
            # Calculate active time (sum of gaps <= 15 minutes)
            active_seconds = 0
            for i in range(len(heartbeats) - 1):
                gap = (heartbeats[i + 1].timestamp - heartbeats[i].timestamp).total_seconds()
                if gap <= 900:  # 15 minutes
                    active_seconds += gap
            
            working_hours = active_seconds / 3600
            
            # Calculate productivity (simple metric: active time / total time * 100)
            total_span = (last_activity - first_activity).total_seconds() / 3600
            productivity = (working_hours / total_span * 100) if total_span > 0 else 0
        else:
            first_activity = None
            last_activity = None 
            working_hours = 0
            productivity = 0
        
        # Parse location
        location_text = "Unknown"
        public_ip = "Unknown"
        if latest_log and latest_log.location:
            try:
                location_data = json.loads(latest_log.location)
                public_ip = location_data.get('ip', 'Unknown')
                location_text = f"{location_data.get('city', 'Unknown')}, {location_data.get('region', 'Unknown')}"
            except:
                pass
        
        enhanced_data.append({
            "id": f"D{employee_id:03d}",
            "username": username,
            "status": status,
            "start_time": first_activity.strftime("%H:%M") if first_activity else "--:--",
            "end_time": last_activity.strftime("%H:%M") if last_activity else "--:--", 
            "working_hours": f"{int(working_hours)}h {int((working_hours % 1) * 60)}m",
            "productivity": f"{int(productivity)}%" if productivity > 0 else "--",
            "public_ip": public_ip,
            "location": location_text,
            "last_seen": latest_heartbeat.timestamp if latest_heartbeat else None,
            "raw_hours": working_hours,
            "raw_productivity": productivity
        })
        employee_id += 1
    
    return {"employees": enhanced_data}

@app.get("/api/admin/employees/status")
def get_employee_status(admin=Depends(verify_admin_token), db: Session = Depends(get_db)):
    """Get current online status of all employees with location details"""
    # Get latest heartbeat for each employee
    latest_heartbeats = db.query(
        EmployeeHeartbeat.username,
        func.max(EmployeeHeartbeat.timestamp).label('latest_timestamp')
    ).group_by(EmployeeHeartbeat.username).subquery()

    current_status = db.query(EmployeeHeartbeat).join(
        latest_heartbeats,
        and_(
            EmployeeHeartbeat.username == latest_heartbeats.c.username,
            EmployeeHeartbeat.timestamp == latest_heartbeats.c.latest_timestamp
        )
    ).all()

    # Determine online status (online if heartbeat within last 10 minutes)
    cutoff_time = datetime.utcnow() - timedelta(minutes=10)
    employees = []

    for heartbeat in current_status:
        is_online = heartbeat.timestamp > cutoff_time

        # Get latest log entry for location details
        latest_log = db.query(EmployeeLog).filter(
            EmployeeLog.username == heartbeat.username
        ).order_by(desc(EmployeeLog.timestamp)).first()

        # Parse location data if available
        public_ip = "Unknown"
        city = "Unknown"
        state = "Unknown"
        country = "Unknown"

        if latest_log and latest_log.location:
            try:
                location_data = json.loads(latest_log.location)
                public_ip = location_data.get('ip', 'Unknown')
                city = location_data.get('city', 'Unknown')
                state = location_data.get('region', 'Unknown')
                country = location_data.get('country', 'Unknown')
            except (json.JSONDecodeError, AttributeError):
                pass

        employees.append({
            "username": heartbeat.username,
            "hostname": heartbeat.hostname,
            "status": "online" if is_online else "offline",
            "last_seen": heartbeat.timestamp,
            "last_heartbeat": heartbeat.timestamp,
            "public_ip": public_ip,
            "city": city,
            "state": state,
            "country": country,
            "location_updated": latest_log.timestamp if latest_log else None
        })

    return {"employees": employees}

@app.get("/api/admin/employees/{username}/logs")
def get_employee_logs(
    username: str,
    days: int = 7,
    admin=Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Get detailed logs for a specific employee"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    logs = db.query(EmployeeLog).filter(
        EmployeeLog.username == username,
        EmployeeLog.timestamp > cutoff_date
    ).order_by(desc(EmployeeLog.timestamp)).all()

    return {"username": username, "logs": logs}

@app.get("/api/admin/employees/{username}/working-hours")
def get_working_hours(
    username: str,
    date: Optional[str] = None,
    admin=Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Calculate working hours for an employee based on heartbeats"""
    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    else:
        target_date = datetime.utcnow().date()

    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = start_of_day + timedelta(days=1)

    heartbeats = db.query(EmployeeHeartbeat).filter(
        EmployeeHeartbeat.username == username,
        EmployeeHeartbeat.timestamp >= start_of_day,
        EmployeeHeartbeat.timestamp < end_of_day
    ).order_by(EmployeeHeartbeat.timestamp).all()

    if not heartbeats:
        return {
            "username": username,
            "date": target_date.isoformat(),
            "total_hours": 0,
            "first_seen": None,
            "last_seen": None
        }

    first_heartbeat = heartbeats[0].timestamp
    last_heartbeat = heartbeats[-1].timestamp

    # Calculate working hours (assuming continuous work between first and last heartbeat)
    total_seconds = (last_heartbeat - first_heartbeat).total_seconds()
    total_hours = total_seconds / 3600  # Convert to hours

    return {
        "username": username,
        "date": target_date.isoformat(),
        "total_hours": round(total_hours, 2),
        "first_seen": first_heartbeat,
        "last_seen": last_heartbeat
    }

@app.get("/api/admin/cleanup")
def cleanup_old_data(admin=Depends(verify_admin_token), db: Session = Depends(get_db)):
    """Clean up data older than 45 days"""
    cutoff_date = datetime.utcnow() - timedelta(days=45)

    # Delete old heartbeats
    old_heartbeats = db.query(EmployeeHeartbeat).filter(
        EmployeeHeartbeat.timestamp < cutoff_date
    ).delete()

    # Delete old logs and their screenshots
    old_logs = db.query(EmployeeLog).filter(
        EmployeeLog.timestamp < cutoff_date
    ).all()

    deleted_screenshots = 0
    for log in old_logs:
        if log.screenshot_path and os.path.exists(log.screenshot_path):
            os.remove(log.screenshot_path)
            deleted_screenshots += 1

    # Delete log records
    deleted_logs = db.query(EmployeeLog).filter(
        EmployeeLog.timestamp < cutoff_date
    ).delete()

    db.commit()

    return {
        "deleted_heartbeats": old_heartbeats,
        "deleted_logs": deleted_logs,
        "deleted_screenshots": deleted_screenshots
    }

# Enhanced reporting endpoints
@app.get("/api/admin/reports/daily")
def get_daily_report(
    date: Optional[str] = None,
    admin=Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Get daily activity report for all employees"""
    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    else:
        target_date = datetime.utcnow().date()

    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = start_of_day + timedelta(days=1)

    # Get all employees who were active on this date
    employees_with_activity = db.query(EmployeeHeartbeat.username).filter(
        EmployeeHeartbeat.timestamp >= start_of_day,
        EmployeeHeartbeat.timestamp < end_of_day
    ).distinct().all()

    report_data = []
    total_hours = 0

    for (username,) in employees_with_activity:
        # Get working hours
        heartbeats = db.query(EmployeeHeartbeat).filter(
            EmployeeHeartbeat.username == username,
            EmployeeHeartbeat.timestamp >= start_of_day,
            EmployeeHeartbeat.timestamp < end_of_day
        ).order_by(EmployeeHeartbeat.timestamp).all()

        if heartbeats:
            first_heartbeat = heartbeats[0].timestamp
            last_heartbeat = heartbeats[-1].timestamp
            hours_worked = (last_heartbeat - first_heartbeat).total_seconds() / 3600
            total_hours += hours_worked

            # Get detailed logs count
            logs_count = db.query(EmployeeLog).filter(
                EmployeeLog.username == username,
                EmployeeLog.timestamp >= start_of_day,
                EmployeeLog.timestamp < end_of_day
            ).count()

            report_data.append({
                "username": username,
                "hours_worked": round(hours_worked, 2),
                "first_activity": first_heartbeat,
                "last_activity": last_heartbeat,
                "heartbeats_count": len(heartbeats),
                "logs_count": logs_count
            })

    return {
        "date": target_date.isoformat(),
        "total_employees_active": len(report_data),
        "total_hours_worked": round(total_hours, 2),
        "average_hours_per_employee": round(total_hours / len(report_data), 2) if report_data else 0,
        "employees": report_data
    }

@app.get("/api/admin/reports/weekly")
def get_weekly_report(
    start_date: Optional[str] = None,
    admin=Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Get weekly activity report for all employees"""
    if start_date:
        week_start = datetime.strptime(start_date, "%Y-%m-%d").date()
    else:
        today = datetime.utcnow().date()
        week_start = today - timedelta(days=today.weekday())

    week_end = week_start + timedelta(days=7)
    start_datetime = datetime.combine(week_start, datetime.min.time())
    end_datetime = datetime.combine(week_end, datetime.min.time())

    # Get all employees with activity in this week
    employees_with_activity = db.query(EmployeeHeartbeat.username).filter(
        EmployeeHeartbeat.timestamp >= start_datetime,
        EmployeeHeartbeat.timestamp < end_datetime
    ).distinct().all()

    report_data = []

    for (username,) in employees_with_activity:
        daily_data = []
        total_week_hours = 0

        # Get data for each day of the week
        for day_offset in range(7):
            current_date = week_start + timedelta(days=day_offset)
            day_start = datetime.combine(current_date, datetime.min.time())
            day_end = day_start + timedelta(days=1)

            heartbeats = db.query(EmployeeHeartbeat).filter(
                EmployeeHeartbeat.username == username,
                EmployeeHeartbeat.timestamp >= day_start,
                EmployeeHeartbeat.timestamp < day_end
            ).order_by(EmployeeHeartbeat.timestamp).all()

            if heartbeats:
                first_heartbeat = heartbeats[0].timestamp
                last_heartbeat = heartbeats[-1].timestamp
                day_hours = (last_heartbeat - first_heartbeat).total_seconds() / 3600
                total_week_hours += day_hours

                daily_data.append({
                    "date": current_date.isoformat(),
                    "hours_worked": round(day_hours, 2),
                    "heartbeats_count": len(heartbeats)
                })
            else:
                daily_data.append({
                    "date": current_date.isoformat(),
                    "hours_worked": 0,
                    "heartbeats_count": 0
                })

        report_data.append({
            "username": username,
            "total_hours": round(total_week_hours, 2),
            "average_daily_hours": round(total_week_hours / 7, 2),
            "daily_breakdown": daily_data
        })

    return {
        "week_start": week_start.isoformat(),
        "week_end": (week_end - timedelta(days=1)).isoformat(),
        "total_employees": len(report_data),
        "employees": report_data
    }

@app.get("/api/admin/reports/range")
def get_range_report(
    start_date: str,
    end_date: str,
    admin=Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Get activity report for custom date range"""
    start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
    end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

    # Get summary statistics
    total_heartbeats = db.query(EmployeeHeartbeat).filter(
        EmployeeHeartbeat.timestamp >= start_datetime,
        EmployeeHeartbeat.timestamp < end_datetime
    ).count()

    total_logs = db.query(EmployeeLog).filter(
        EmployeeLog.timestamp >= start_datetime,
        EmployeeLog.timestamp < end_datetime
    ).count()

    unique_employees = db.query(EmployeeHeartbeat.username).filter(
        EmployeeHeartbeat.timestamp >= start_datetime,
        EmployeeHeartbeat.timestamp < end_datetime
    ).distinct().count()

    # Get per-employee breakdown
    employees_with_activity = db.query(EmployeeHeartbeat.username).filter(
        EmployeeHeartbeat.timestamp >= start_datetime,
        EmployeeHeartbeat.timestamp < end_datetime
    ).distinct().all()

    employee_data = []

    for (username,) in employees_with_activity:
        heartbeats = db.query(EmployeeHeartbeat).filter(
            EmployeeHeartbeat.username == username,
            EmployeeHeartbeat.timestamp >= start_datetime,
            EmployeeHeartbeat.timestamp < end_datetime
        ).order_by(EmployeeHeartbeat.timestamp).all()

        logs_count = db.query(EmployeeLog).filter(
            EmployeeLog.username == username,
            EmployeeLog.timestamp >= start_datetime,
            EmployeeLog.timestamp < end_datetime
        ).count()

        if heartbeats:
            first_activity = heartbeats[0].timestamp
            last_activity = heartbeats[-1].timestamp

            # Calculate total active time (sum of gaps < 15 minutes)
            active_time = 0
            for i in range(len(heartbeats) - 1):
                gap = (heartbeats[i + 1].timestamp - heartbeats[i].timestamp).total_seconds()
                if gap <= 900:  # 15 minutes or less
                    active_time += gap

            employee_data.append({
                "username": username,
                "heartbeats_count": len(heartbeats),
                "logs_count": logs_count,
                "estimated_active_hours": round(active_time / 3600, 2),
                "first_activity": first_activity,
                "last_activity": last_activity
            })

    return {
        "start_date": start_date,
        "end_date": end_date,
        "duration_days": (end_datetime - start_datetime).days,
        "summary": {
            "total_heartbeats": total_heartbeats,
            "total_logs": total_logs,
            "unique_employees": unique_employees
        },
        "employees": employee_data
    }

# Test endpoint for debugging
@app.get("/api/download/test")
def test_download():
    return {"message": "Download endpoint works"}

# Agent download endpoints
@app.get("/api/download/agent/{platform}")
def download_agent(platform: str, admin=Depends(verify_admin_token)):
    """Download agent installer for specified platform"""
    import zipfile
    import io

    if platform not in ['windows', 'mac', 'linux']:
        raise HTTPException(status_code=400, detail="Invalid platform")

    # Create agent installer package in memory
    zip_buffer = io.BytesIO()

    try:
        # Read agent file content
        agent_paths = ['../agent/agent.py', 'agent/agent.py', './agent/agent.py']
        agent_content = None

        for path in agent_paths:
            try:
                with open(path, 'r') as f:
                    agent_content = f.read()
                break
            except FileNotFoundError:
                continue

        if not agent_content:
            # Create a basic agent if file not found
            agent_content = '''#!/usr/bin/env python3
"""
WFH Employee Monitoring Agent
Basic version - Update SERVER_URL and AUTH_TOKEN before use
"""

import requests
import time
import socket
import getpass
from datetime import datetime

SERVER_URL = "https://your-repl-url.replit.app"
AUTH_TOKEN = "agent-secret-token-change-this-in-production"

def send_heartbeat():
    data = {
        "username": getpass.getuser(),
        "hostname": socket.gethostname(),
        "status": "online"
    }

    try:
        response = requests.post(
            f"{SERVER_URL}/api/heartbeat",
            json=data,
            headers={'Authorization': f'Bearer {AUTH_TOKEN}'},
            timeout=30
        )
        print(f"Heartbeat: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Starting WFH Monitoring Agent...")
    while True:
        send_heartbeat()
        time.sleep(300)  # 5 minutes
'''

        # Update server URL in agent content with current deployment URL
        repl_id = os.getenv("REPL_ID", "")
        repl_slug = os.getenv("REPL_SLUG", "")

        # Try to get the current server URL from the request
        current_url = "https://e1cdd19c-fdf6-4b9f-94bf-b122742d048e-00-2ltrq5fmw548e.riker.replit.dev"

        # Replace the placeholder URL with the actual server URL
        agent_content = agent_content.replace(
            'SERVER_URL = "https://your-repl-name.replit.app"',
            f'SERVER_URL = "{current_url}"'
        )

        # Read requirements file content
        requirements_paths = ['../agent/agent_requirements.txt', 'agent/agent_requirements.txt', './agent/agent_requirements.txt']
        requirements_content = None

        for path in requirements_paths:
            try:
                with open(path, 'r') as f:
                    requirements_content = f.read()
                break
            except FileNotFoundError:
                continue

        if not requirements_content:
            # Create basic requirements if file not found
            requirements_content = """requests>=2.31.0
schedule>=1.2.0
Pillow>=10.0.0
psutil>=5.9.0
"""

        # Create ZIP file with all content
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('agent.py', agent_content)
            zip_file.writestr('agent_requirements.txt', requirements_content)

        # Add platform-specific instructions
            instructions = f"""
# WFH Monitoring Agent Setup - {platform.title()}

## Installation Instructions

1. Ensure Python 3.7+ is installed on this machine
2. Extract these files to a directory (e.g., C:\\wfh-agent\\ on Windows)
3. Open command prompt/terminal in that directory
4. Run: pip install -r agent_requirements.txt
5. Edit agent.py to set your server URL if needed
6. Run: python agent.py
7. The agent will start sending heartbeats every 5 minutes

## Configuration
- Server URL: {os.getenv('REPL_SLUG', 'your-server-url')}
- Agent Token: agent-secret-token-change-this-in-production

## Platform-specific Notes:
"""

            if platform == 'windows':
                instructions += """
### Windows Setup:
- Run as Administrator for best compatibility
- Add to Windows startup: Add shortcut to agent.py in:
  %APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\
- For service installation, use nssm or similar tools
"""

                # Windows service installation script
                windows_script = """@echo off
echo Installing WFH Monitoring Agent for Windows...
echo.

echo Step 1: Installing Python dependencies...
pip install -r agent_requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to install dependencies. Please ensure Python and pip are installed.
    pause
    exit /b 1
)

echo.
echo Step 2: Agent ready to run...
echo Run: python agent.py
echo To run in background: start /b python agent.py
echo.
echo For Windows Service installation:
echo Run as Administrator: install_service_windows.bat
pause
"""
                zip_file.writestr('install.bat', windows_script)

                # Add Windows service installer
                service_installer = """@echo off
echo Installing WFH Agent as Windows Service...
echo This requires Administrator privileges.
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Administrator privileges confirmed.
) else (
    echo ERROR: This script requires Administrator privileges.
    echo Please run as Administrator.
    pause
    exit /b 1
)

echo.
echo Installing Python dependencies...
pip install -r agent_requirements.txt
pip install pywin32

echo.
echo Installing service...
python service_wrapper.py install

echo.
echo Starting WFH Agent service...
python service_wrapper.py start

echo.
echo WFH Agent service installed and started successfully.
echo Service will start automatically on system boot.
echo.
echo To manage the service:
echo   Start:   python service_wrapper.py start
echo   Stop:    python service_wrapper.py stop
echo   Remove:  python service_wrapper.py remove
pause
"""
                zip_file.writestr('install_service_windows.bat', service_installer)

                # Add service wrapper
                try:
                    with open('../agent/service_wrapper.py', 'r') as f:
                        service_wrapper_content = f.read()
                    zip_file.writestr('service_wrapper.py', service_wrapper_content)
                except FileNotFoundError:
                    # Create basic service wrapper if file not found
                    service_wrapper_content = '''#!/usr/bin/env python3
"""
Windows Service Wrapper for WFH Agent
"""

import sys
import os
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import subprocess
import time

class WFHAgentService(win32serviceutil.ServiceFramework):
    _svc_name_ = "WFHAgent"
    _svc_display_name_ = "WFH Monitoring Agent"
    _svc_description_ = "Work From Home Employee Monitoring Agent"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_alive = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_alive = False

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        self.main()

    def main(self):
        # Get the directory where the service is running
        service_dir = os.path.dirname(os.path.abspath(__file__))
        agent_path = os.path.join(service_dir, 'agent.py')

        while self.is_alive:
            try:
                # Start the agent process
                process = subprocess.Popen([sys.executable, agent_path], 
                                         cwd=service_dir,
                                         stdout=subprocess.PIPE, 
                                         stderr=subprocess.PIPE)

                # Wait for process to complete or service to stop
                while self.is_alive and process.poll() is None:
                    time.sleep(1)

                if not self.is_alive:
                    process.terminate()
                    break

                # If process died, wait before restarting
                if self.is_alive:
                    time.sleep(30)

            except Exception as e:
                servicemanager.LogErrorMsg(f"Service error: {e}")
                if self.is_alive:
                    time.sleep(60)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(WFHAgentService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(WFHAgentService)
'''
                    zip_file.writestr('service_wrapper.py', service_wrapper_content)

            elif platform == 'mac':
                instructions += """
### macOS Setup:
- May need to allow Python in Privacy & Security settings
- For startup: Create LaunchAgent plist file in ~/Library/LaunchAgents/
- Grant screen recording permissions in System Preferences
"""

                # macOS installation script
                mac_script = """#!/bin/bash
echo "Installing WFH Monitoring Agent for macOS..."
echo

echo "Step 1: Installing Python dependencies..."
pip3 install -r agent_requirements.txt

echo
echo "Step 2: Agent ready to run..."
echo "Run: python3 agent.py"
echo "To run in background: nohup python3 agent.py > agent.log 2>&1 &"
"""
                zip_file.writestr('install.sh', mac_script)

            elif platform == 'linux':
                instructions += """
### Linux Setup:
- Install python3-pip if not available: sudo apt install python3-pip
- For startup: Create systemd service or add to ~/.profile
- May need to install python3-tk for screenshot functionality
"""

                # Linux installation script
                linux_script = """#!/bin/bash
echo "Installing WFH Monitoring Agent for Linux..."
echo

echo "Step 1: Installing Python dependencies..."
pip3 install -r agent_requirements.txt

echo
echo "Step 2: Agent ready to run..."
echo "Run: python3 agent.py"
echo "To run in background: nohup python3 agent.py > agent.log 2>&1 &"
"""
                zip_file.writestr('install.sh', linux_script)

            zip_file.writestr('README.txt', instructions)

        zip_buffer.seek(0)
        return StreamingResponse(
            io.BytesIO(zip_buffer.read()),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=wfh-agent-{platform}.zip"}
        )

    except Exception as e:
        print(f"Error creating agent package: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create agent package: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)