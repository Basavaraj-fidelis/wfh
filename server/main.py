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

# Create FastAPI app
app = FastAPI(title="WFH Employee Monitoring System", version="1.0.0")

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

class AdminLogin(BaseModel):
    username: str
    password: str

class WorkingHoursResponse(BaseModel):
    username: str
    date: str
    total_hours: float
    first_seen: datetime
    last_seen: datetime

# Initialize database on startup
@app.on_event("startup")
def startup_event():
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
    screenshot: UploadFile = File(...),
    agent_auth=Depends(verify_agent_token),
    db: Session = Depends(get_db)
):
    """Receive detailed log with screenshot from agent"""
    try:
        print(f"Received detailed log from {username}@{hostname}")
        print(f"IPs: local={local_ip}, public={public_ip}")
        print(f"Location: {location}")
        
        # Save screenshot
        timestamp = datetime.utcnow()
        filename = f"{username}_{timestamp.strftime('%Y%m%d_%H%M%S')}.png"
        screenshot_path = os.path.join(screenshots_dir, filename)
        
        print(f"Saving screenshot to: {screenshot_path}")
        
        with open(screenshot_path, "wb") as buffer:
            content = screenshot.file.read()
            buffer.write(content)
            print(f"Screenshot saved, size: {len(content)} bytes")
        
        # Save log to database
        log_record = EmployeeLog(
            username=username,
            hostname=hostname,
            local_ip=local_ip,
            public_ip=public_ip,
            location=location,
            screenshot_path=screenshot_path,
            timestamp=timestamp
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

# Admin dashboard with proper navigation and sections
@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>WFH Employee Monitoring - Admin Dashboard</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: #f5f5f5;
                color: #333;
            }
            
            .login-container {
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }
            
            .login-box {
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 15px 35px rgba(0,0,0,0.1);
                width: 100%;
                max-width: 400px;
            }
            
            .login-box h2 {
                text-align: center;
                margin-bottom: 30px;
                color: #333;
                font-weight: 300;
            }
            
            .form-group {
                margin-bottom: 20px;
            }
            
            .form-group label {
                display: block;
                margin-bottom: 5px;
                font-weight: 500;
            }
            
            .form-group input {
                width: 100%;
                padding: 12px;
                border: 1px solid #ddd;
                border-radius: 5px;
                font-size: 14px;
            }
            
            .btn-primary {
                width: 100%;
                padding: 12px;
                background: #667eea;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                cursor: pointer;
                transition: background 0.3s;
            }
            
            .btn-primary:hover {
                background: #5a6fd8;
            }
            
            .dashboard {
                display: none;
                min-height: 100vh;
            }
            
            .sidebar {
                position: fixed;
                left: 0;
                top: 0;
                width: 250px;
                height: 100vh;
                background: #2c3e50;
                color: white;
                overflow-y: auto;
            }
            
            .sidebar-header {
                padding: 20px;
                background: #34495e;
                border-bottom: 1px solid #3d566e;
            }
            
            .sidebar-header h3 {
                font-size: 18px;
                font-weight: 300;
            }
            
            .nav-menu {
                list-style: none;
                padding: 0;
            }
            
            .nav-menu li {
                border-bottom: 1px solid #3d566e;
            }
            
            .nav-menu a {
                display: block;
                padding: 15px 20px;
                color: #ecf0f1;
                text-decoration: none;
                transition: background 0.3s;
            }
            
            .nav-menu a:hover,
            .nav-menu a.active {
                background: #34495e;
                color: #3498db;
            }
            
            .main-content {
                margin-left: 250px;
                padding: 20px;
            }
            
            .header {
                background: white;
                padding: 20px;
                border-radius: 5px;
                margin-bottom: 20px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .content-section {
                display: none;
                background: white;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            
            .content-section.active {
                display: block;
            }
            
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            
            .stat-card {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 5px;
                text-align: center;
            }
            
            .stat-card h3 {
                font-size: 24px;
                margin-bottom: 10px;
            }
            
            .table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }
            
            .table th,
            .table td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            
            .table th {
                background: #f8f9fa;
                font-weight: 500;
            }
            
            .status-online {
                color: #28a745;
                font-weight: bold;
            }
            
            .status-offline {
                color: #dc3545;
                font-weight: bold;
            }
            
            .btn {
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                font-size: 14px;
            }
            
            .btn-success {
                background: #28a745;
                color: white;
            }
            
            .btn-danger {
                background: #dc3545;
                color: white;
            }
            
            .btn-primary-sm {
                background: #007bff;
                color: white;
            }
            
            .download-card {
                border: 1px solid #ddd;
                padding: 20px;
                margin: 20px 0;
                border-radius: 5px;
            }
            
            .form-row {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin-bottom: 20px;
            }
            
            .alert {
                padding: 15px;
                margin-bottom: 20px;
                border-radius: 4px;
            }
            
            .alert-success {
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            
            .alert-error {
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
            
            /* Enhanced UI Styles */
            .search-filter-bar {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
                display: flex;
                gap: 15px;
                flex-wrap: wrap;
                align-items: center;
            }
            
            .search-box {
                flex: 1;
                min-width: 200px;
            }
            
            .search-box input {
                width: 100%;
                padding: 8px 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            }
            
            .filter-select {
                min-width: 150px;
            }
            
            .filter-select select {
                padding: 8px 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
                font-size: 14px;
            }
            
            .date-picker {
                display: flex;
                gap: 10px;
                align-items: center;
            }
            
            .date-picker input {
                padding: 8px 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            }
            
            .report-tabs {
                display: flex;
                border-bottom: 1px solid #ddd;
                margin-bottom: 20px;
            }
            
            .report-tab {
                padding: 12px 20px;
                background: none;
                border: none;
                cursor: pointer;
                font-size: 14px;
                color: #666;
                border-bottom: 3px solid transparent;
                transition: all 0.3s;
            }
            
            .report-tab.active {
                color: #007bff;
                border-bottom-color: #007bff;
            }
            
            .report-tab:hover {
                color: #007bff;
                background: #f8f9fa;
            }
            
            .chart-container {
                background: white;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }
            
            .progress-bar {
                width: 100%;
                height: 20px;
                background: #f8f9fa;
                border-radius: 10px;
                overflow: hidden;
                position: relative;
            }
            
            .progress-fill {
                height: 100%;
                transition: width 0.3s;
                border-radius: 10px;
            }
            
            .progress-text {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                font-size: 12px;
                font-weight: bold;
                color: #333;
            }
            
            .export-buttons {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
            }
            
            .summary-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 15px;
                margin-bottom: 20px;
            }
            
            .summary-card {
                background: white;
                padding: 15px;
                border-radius: 5px;
                border: 1px solid #ddd;
                text-align: center;
            }
            
            .summary-card h4 {
                margin: 0 0 10px 0;
                color: #333;
                font-size: 18px;
            }
            
            .summary-card .value {
                font-size: 24px;
                font-weight: bold;
                color: #007bff;
            }
            
            .employee-card {
                background: white;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 15px;
                margin-bottom: 10px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .employee-info {
                flex: 1;
            }
            
            .employee-actions {
                display: flex;
                gap: 5px;
            }
        </style>
    </head>
    <body>
        <!-- Login Screen -->
        <div id="loginScreen" class="login-container">
            <div class="login-box">
                <h2>Admin Login</h2>
                <div id="loginAlert"></div>
                <form onsubmit="login(event)">
                    <div class="form-group">
                        <label for="username">Username</label>
                        <input type="text" id="username" name="username" value="admin" required>
                    </div>
                    <div class="form-group">
                        <label for="password">Password</label>
                        <input type="password" id="password" name="password" value="admin123" required>
                    </div>
                    <button type="submit" class="btn-primary">Login</button>
                </form>
            </div>
        </div>
        
        <!-- Dashboard -->
        <div id="dashboardScreen" class="dashboard">
            <div class="sidebar">
                <div class="sidebar-header">
                    <h3>WFH Monitor</h3>
                    <p>Admin Panel</p>
                </div>
                <ul class="nav-menu">
                    <li><a href="#" onclick="showSection('dashboard')" class="active">📊 Dashboard</a></li>
                    <li><a href="#" onclick="showSection('users')">👥 Employees</a></li>
                    <li><a href="#" onclick="showSection('reports')">📈 Reports</a></li>
                    <li><a href="#" onclick="showSection('agent')">💾 Agent Download</a></li>
                    <li><a href="#" onclick="showSection('settings')">⚙️ Settings</a></li>
                    <li><a href="#" onclick="logout()">🚪 Logout</a></li>
                </ul>
            </div>
            
            <div class="main-content">
                <div class="header">
                    <div>
                        <h1 id="pageTitle">Dashboard</h1>
                        <p>Welcome to the WFH Employee Monitoring System</p>
                    </div>
                    <div>
                        <span>Admin User</span>
                        <button class="btn btn-danger" onclick="logout()">Logout</button>
                    </div>
                </div>
                
                <!-- Dashboard Section -->
                <div id="dashboardSection" class="content-section active">
                    <div class="stats-grid">
                        <div class="stat-card">
                            <h3 id="totalEmployees">-</h3>
                            <p>Total Employees</p>
                        </div>
                        <div class="stat-card">
                            <h3 id="onlineEmployees">-</h3>
                            <p>Online Now</p>
                        </div>
                        <div class="stat-card">
                            <h3 id="offlineEmployees">-</h3>
                            <p>Offline</p>
                        </div>
                        <div class="stat-card">
                            <h3 id="totalLogs">-</h3>
                            <p>Total Logs Today</p>
                        </div>
                    </div>
                    
                    <h3>Recent Employee Activity</h3>
                    <div id="recentActivity">Loading...</div>
                </div>
                
                <!-- Users Section -->
                <div id="usersSection" class="content-section">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h3>Employee Management</h3>
                        <button class="btn btn-success" onclick="refreshEmployees()">🔄 Refresh</button>
                    </div>
                    
                    <!-- Search and Filter Bar -->
                    <div class="search-filter-bar">
                        <div class="search-box">
                            <input type="text" id="employeeSearch" placeholder="Search employees by name or hostname..." oninput="filterEmployees()">
                        </div>
                        <div class="filter-select">
                            <select id="statusFilter" onchange="filterEmployees()">
                                <option value="">All Status</option>
                                <option value="online">Online</option>
                                <option value="offline">Offline</option>
                            </select>
                        </div>
                        <div class="filter-select">
                            <select id="sortBy" onchange="sortEmployees()">
                                <option value="name">Sort by Name</option>
                                <option value="status">Sort by Status</option>
                                <option value="lastSeen">Sort by Last Seen</option>
                                <option value="location">Sort by Location</option>
                            </select>
                        </div>
                    </div>
                    
                    <div id="employeesList">Loading employees...</div>
                </div>
                
                <!-- Reports Section -->
                <div id="reportsSection" class="content-section">
                    <h3>Reports & Analytics</h3>
                    
                    <!-- Report Tabs -->
                    <div class="report-tabs">
                        <button class="report-tab active" onclick="showReportTab('daily')">Daily Reports</button>
                        <button class="report-tab" onclick="showReportTab('weekly')">Weekly Reports</button>
                        <button class="report-tab" onclick="showReportTab('monthly')">Monthly Reports</button>
                        <button class="report-tab" onclick="showReportTab('custom')">Custom Range</button>
                    </div>
                    
                    <!-- Daily Reports Tab -->
                    <div id="dailyReportTab" class="report-content active">
                        <div class="date-picker">
                            <label>Select Date:</label>
                            <input type="date" id="dailyDate" onchange="loadDailyReport()">
                            <button class="btn btn-primary-sm" onclick="loadDailyReport()">Generate Report</button>
                        </div>
                        <div id="dailyReportContent"></div>
                    </div>
                    
                    <!-- Weekly Reports Tab -->
                    <div id="weeklyReportTab" class="report-content" style="display: none;">
                        <div class="date-picker">
                            <label>Select Week Starting:</label>
                            <input type="date" id="weeklyDate" onchange="loadWeeklyReport()">
                            <button class="btn btn-primary-sm" onclick="loadWeeklyReport()">Generate Report</button>
                        </div>
                        <div id="weeklyReportContent"></div>
                    </div>
                    
                    <!-- Monthly Reports Tab -->
                    <div id="monthlyReportTab" class="report-content" style="display: none;">
                        <div class="date-picker">
                            <label>Select Month:</label>
                            <input type="month" id="monthlyDate" onchange="loadMonthlyReport()">
                            <button class="btn btn-primary-sm" onclick="loadMonthlyReport()">Generate Report</button>
                        </div>
                        <div id="monthlyReportContent"></div>
                    </div>
                    
                    <!-- Custom Range Tab -->
                    <div id="customReportTab" class="report-content" style="display: none;">
                        <div class="date-picker">
                            <label>From:</label>
                            <input type="date" id="customFromDate">
                            <label>To:</label>
                            <input type="date" id="customToDate">
                            <button class="btn btn-primary-sm" onclick="loadCustomReport()">Generate Report</button>
                        </div>
                        <div id="customReportContent"></div>
                    </div>
                </div>
                
                <!-- Agent Download Section -->
                <div id="agentSection" class="content-section">
                    <h3>Agent Download & Setup</h3>
                    <p>Download the monitoring agent to install on employee computers.</p>
                    
                    <div class="download-card">
                        <h4>Windows Agent (.msi)</h4>
                        <p>For Windows 7/8/10/11 systems</p>
                        <p><strong>Silent Install:</strong> <code>msiexec /i agent.msi /qn</code></p>
                        <button class="btn btn-primary-sm" onclick="downloadAgent('windows')">Download Windows Installer</button>
                    </div>
                    
                    <div class="download-card">
                        <h4>macOS Agent (.pkg)</h4>
                        <p>For macOS 10.12 and newer</p>
                        <p><strong>Install:</strong> Double-click to install or <code>sudo installer -pkg agent.pkg -target /</code></p>
                        <button class="btn btn-primary-sm" onclick="downloadAgent('mac')">Download macOS Package</button>
                    </div>
                    
                    <div class="download-card">
                        <h4>Linux Agent (.deb)</h4>
                        <p>For Ubuntu, Debian, and derivatives</p>
                        <p><strong>Install:</strong> <code>sudo dpkg -i agent.deb</code></p>
                        <button class="btn btn-primary-sm" onclick="downloadAgent('linux')">Download Linux Package</button>
                    </div>
                    
                    <div style="margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 5px;">
                        <h4>Installation Instructions</h4>
                        <ol>
                            <li>Download the appropriate agent for your system</li>
                            <li>Install Python 3.7+ on the target machine</li>
                            <li>Extract the agent files to a directory</li>
                            <li>Run: <code>pip install -r agent_requirements.txt</code></li>
                            <li>Update the server URL in the agent configuration</li>
                            <li>Run: <code>python agent.py</code> to start monitoring</li>
                        </ol>
                        
                        <h4 style="margin-top: 20px;">Configuration</h4>
                        <p><strong>Server URL:</strong> <span id="serverUrl">${window.location.origin}</span></p>
                        <p><strong>Agent Token:</strong> <code>agent-secret-token-change-this-in-production</code></p>
                    </div>
                </div>
                
                <!-- Settings Section -->
                <div id="settingsSection" class="content-section">
                    <h3>System Settings</h3>
                    
                    <div class="form-row">
                        <div>
                            <label>Data Retention Period (days)</label>
                            <input type="number" id="retentionDays" value="45" min="1" max="365">
                        </div>
                        <div>
                            <label>Heartbeat Interval (minutes)</label>
                            <input type="number" id="heartbeatInterval" value="5" min="1" max="60">
                        </div>
                    </div>
                    
                    <div class="form-row">
                        <div>
                            <label>Agent Token</label>
                            <input type="text" id="agentToken" value="agent-secret-token-change-this-in-production">
                        </div>
                        <div>
                            <label>Screenshot Quality</label>
                            <select id="screenshotQuality">
                                <option value="high">High</option>
                                <option value="medium" selected>Medium</option>
                                <option value="low">Low</option>
                            </select>
                        </div>
                    </div>
                    
                    <div style="margin-top: 30px;">
                        <button class="btn btn-success" onclick="saveSettings()">💾 Save Settings</button>
                        <button class="btn btn-danger" onclick="cleanupOldData()">🗑️ Cleanup Old Data</button>
                    </div>
                    
                    <div id="settingsAlert"></div>
                </div>
            </div>
        </div>
        
        <script>
            let authToken = localStorage.getItem('adminToken') || '';
            let currentSection = 'dashboard';
            let allEmployees = [];
            let filteredEmployees = [];
            let currentReportTab = 'daily';
            
            // Check if already logged in
            if (authToken) {
                showDashboard();
                loadDashboardData();
            }
            
            // Set default dates
            document.addEventListener('DOMContentLoaded', function() {
                const today = new Date().toISOString().split('T')[0];
                const thisWeek = new Date();
                thisWeek.setDate(thisWeek.getDate() - thisWeek.getDay());
                const weekStart = thisWeek.toISOString().split('T')[0];
                const thisMonth = new Date().toISOString().substr(0, 7);
                
                if(document.getElementById('dailyDate')) document.getElementById('dailyDate').value = today;
                if(document.getElementById('weeklyDate')) document.getElementById('weeklyDate').value = weekStart;
                if(document.getElementById('monthlyDate')) document.getElementById('monthlyDate').value = thisMonth;
            });
            
            async function login(event) {
                event.preventDefault();
                
                // Clear any previous alerts
                document.getElementById('loginAlert').innerHTML = '';
                
                const username = document.getElementById('username').value.trim();
                const password = document.getElementById('password').value;
                
                // Basic validation
                if (!username || !password) {
                    showAlert('loginAlert', 'Please enter both username and password', 'error');
                    return;
                }
                
                // Show loading state
                const loginButton = event.target.querySelector('button[type="submit"]');
                const originalText = loginButton.textContent;
                loginButton.textContent = 'Logging in...';
                loginButton.disabled = true;
                
                try {
                    console.log('Attempting login with username:', username);
                    
                    const response = await fetch('/api/admin/login', {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json',
                            'Accept': 'application/json'
                        },
                        body: JSON.stringify({ username, password })
                    });
                    
                    console.log('Login response status:', response.status);
                    const responseData = await response.text();
                    console.log('Login response data:', responseData);
                    
                    if (response.ok) {
                        const data = JSON.parse(responseData);
                        if (data.access_token) {
                            authToken = data.access_token;
                            localStorage.setItem('adminToken', authToken);
                            console.log('Login successful, token stored');
                            showDashboard();
                            loadDashboardData();
                        } else {
                            showAlert('loginAlert', 'Login response missing token', 'error');
                        }
                    } else {
                        let errorMessage = 'Login failed';
                        try {
                            const errorData = JSON.parse(responseData);
                            errorMessage = errorData.detail || errorMessage;
                        } catch (e) {
                            errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                        }
                        showAlert('loginAlert', errorMessage, 'error');
                    }
                } catch (error) {
                    console.error('Login error:', error);
                    showAlert('loginAlert', 'Connection error: ' + error.message, 'error');
                } finally {
                    // Restore button state
                    loginButton.textContent = originalText;
                    loginButton.disabled = false;
                }
            }
            
            function showDashboard() {
                document.getElementById('loginScreen').style.display = 'none';
                document.getElementById('dashboardScreen').style.display = 'block';
            }
            
            function logout() {
                authToken = '';
                localStorage.removeItem('adminToken');
                document.getElementById('loginScreen').style.display = 'flex';
                document.getElementById('dashboardScreen').style.display = 'none';
            }
            
            function showSection(section) {
                // Update navigation
                document.querySelectorAll('.nav-menu a').forEach(a => a.classList.remove('active'));
                event.target.classList.add('active');
                
                // Hide all sections
                document.querySelectorAll('.content-section').forEach(s => s.classList.remove('active'));
                
                // Show selected section
                document.getElementById(section + 'Section').classList.add('active');
                
                // Update page title
                const titles = {
                    'dashboard': 'Dashboard',
                    'users': 'Employee Management', 
                    'reports': 'Reports & Analytics',
                    'agent': 'Agent Download',
                    'settings': 'System Settings'
                };
                document.getElementById('pageTitle').textContent = titles[section];
                
                currentSection = section;
                
                // Load section-specific data
                if (section === 'users') {
                    loadEmployees();
                } else if (section === 'dashboard') {
                    loadDashboardData();
                } else if (section === 'reports') {
                    // Load current report tab by default
                    if (currentReportTab === 'daily') loadDailyReport();
                }
            }
            
            async function makeAuthenticatedRequest(url, options = {}) {
                try {
                    const response = await fetch(url, {
                        ...options,
                        headers: {
                            'Authorization': 'Bearer ' + authToken,
                            ...options.headers
                        }
                    });
                    
                    if (response.status === 401) {
                        console.log('Token expired, redirecting to login');
                        logout();
                        return null;
                    }
                    
                    return response;
                } catch (error) {
                    console.error('Request failed:', error);
                    return null;
                }
            }

            async function loadDashboardData() {
                try {
                    const response = await makeAuthenticatedRequest('/api/admin/employees/status');
                    
                    if (response && response.ok) {
                        const data = await response.json();
                        const employees = data.employees || [];
                        
                        const online = employees.filter(e => e.status === 'online').length;
                        const offline = employees.filter(e => e.status === 'offline').length;
                        
                        document.getElementById('totalEmployees').textContent = employees.length;
                        document.getElementById('onlineEmployees').textContent = online;
                        document.getElementById('offlineEmployees').textContent = offline;
                        
                        // Show recent activity
                        const activityHtml = employees.map(emp => 
                            `<div style="padding: 10px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between;">
                                <div>
                                    <strong>${emp.username}</strong> (${emp.hostname})
                                </div>
                                <div class="${emp.status === 'online' ? 'status-online' : 'status-offline'}">
                                    ${emp.status === 'online' ? '🟢 Online' : '🔴 Offline'} 
                                    <small>${new Date(emp.last_seen).toLocaleString()}</small>
                                </div>
                            </div>`
                        ).join('');
                        
                        document.getElementById('recentActivity').innerHTML = activityHtml || '<p>No employee data available</p>';
                    } else if (response === null) {
                        // Token expired, user was redirected to login
                        return;
                    }
                } catch (error) {
                    console.error('Failed to load dashboard data:', error);
                }
            }
            
            async function loadEmployees() {
                try {
                    const response = await makeAuthenticatedRequest('/api/admin/employees/status');
                    
                    if (response && response.ok) {
                        const data = await response.json();
                        const employees = data.employees || [];
                        
                        const tableHtml = `
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>Employee</th>
                                        <th>Hostname</th>
                                        <th>Status</th>
                                        <th>Public IP</th>
                                        <th>Location</th>
                                        <th>Last Seen</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${employees.map(emp => `
                                        <tr>
                                            <td><strong>${emp.username}</strong></td>
                                            <td>${emp.hostname}</td>
                                            <td class="${emp.status === 'online' ? 'status-online' : 'status-offline'}">
                                                ${emp.status === 'online' ? '🟢 Online' : '🔴 Offline'}
                                            </td>
                                            <td>${emp.public_ip}</td>
                                            <td>
                                                <div style="font-size: 12px;">
                                                    <div>🏙️ ${emp.city}, ${emp.state}</div>
                                                    <div>🌍 ${emp.country}</div>
                                                </div>
                                            </td>
                                            <td>${new Date(emp.last_seen).toLocaleString()}</td>
                                            <td>
                                                <button class="btn btn-primary-sm" onclick="viewEmployeeLogs('${emp.username}')">View Logs</button>
                                                <button class="btn btn-success" onclick="viewWorkingHours('${emp.username}')">Working Hours</button>
                                            </td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        `;
                        
                        allEmployees = employees;
                        filteredEmployees = [...employees];
                        displayEmployees(filteredEmployees);
                    } else if (response === null) {
                        // Token expired, user was redirected to login
                        return;
                    } else {
                        document.getElementById('employeesList').innerHTML = '<p>Error loading employees</p>';
                    }
                } catch (error) {
                    document.getElementById('employeesList').innerHTML = '<p>Error loading employees</p>';
                }
            }
            
            function displayEmployees(employees) {
                const tableHtml = `
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Employee</th>
                                <th>Hostname</th>
                                <th>Status</th>
                                <th>Public IP</th>
                                <th>Location</th>
                                <th>Last Seen</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${employees.map(emp => `
                                <tr>
                                    <td><strong>${emp.username}</strong></td>
                                    <td>${emp.hostname}</td>
                                    <td class="${emp.status === 'online' ? 'status-online' : 'status-offline'}">
                                        ${emp.status === 'online' ? '🟢 Online' : '🔴 Offline'}
                                    </td>
                                    <td>${emp.public_ip}</td>
                                    <td>
                                        <div style="font-size: 12px;">
                                            <div>🏙️ ${emp.city}, ${emp.state}</div>
                                            <div>🌍 ${emp.country}</div>
                                        </div>
                                    </td>
                                    <td>${new Date(emp.last_seen).toLocaleString()}</td>
                                    <td>
                                        <button class="btn btn-primary-sm" onclick="viewEmployeeLogs('${emp.username}')">View Logs</button>
                                        <button class="btn btn-success" onclick="viewWorkingHours('${emp.username}')">Working Hours</button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
                
                document.getElementById('employeesList').innerHTML = employees.length ? tableHtml : '<p>No employees found</p>';
            }
            
            function filterEmployees() {
                const searchTerm = document.getElementById('employeeSearch').value.toLowerCase();
                const statusFilter = document.getElementById('statusFilter').value;
                
                filteredEmployees = allEmployees.filter(emp => {
                    const matchesSearch = emp.username.toLowerCase().includes(searchTerm) || 
                                        emp.hostname.toLowerCase().includes(searchTerm);
                    const matchesStatus = !statusFilter || emp.status === statusFilter;
                    return matchesSearch && matchesStatus;
                });
                
                sortEmployees();
            }
            
            function sortEmployees() {
                const sortBy = document.getElementById('sortBy').value;
                
                filteredEmployees.sort((a, b) => {
                    switch(sortBy) {
                        case 'name':
                            return a.username.localeCompare(b.username);
                        case 'status':
                            return a.status.localeCompare(b.status);
                        case 'lastSeen':
                            return new Date(b.last_seen) - new Date(a.last_seen);
                        case 'location':
                            return a.city.localeCompare(b.city);
                        default:
                            return 0;
                    }
                });
                
                displayEmployees(filteredEmployees);
            }
            
            function refreshEmployees() {
                loadEmployees();
            }
            
            // Report Tab Functions
            function showReportTab(tabName) {
                // Update tab styling
                document.querySelectorAll('.report-tab').forEach(tab => tab.classList.remove('active'));
                event.target.classList.add('active');
                
                // Hide all tab content
                document.querySelectorAll('.report-content').forEach(content => content.style.display = 'none');
                
                // Show selected tab content
                document.getElementById(tabName + 'ReportTab').style.display = 'block';
                
                currentReportTab = tabName;
            }
            
            async function loadDailyReport() {
                const date = document.getElementById('dailyDate').value;
                if (!date) return;
                
                try {
                    const response = await makeAuthenticatedRequest(`/api/admin/reports/daily?date=${date}`);
                    
                    if (response && response.ok) {
                        const data = await response.json();
                        
                        let reportHtml = `
                            <div class="export-buttons">
                                <button class="btn btn-success" onclick="exportReport('daily', '${date}')">📊 Export CSV</button>
                            </div>
                            
                            <div class="summary-grid">
                                <div class="summary-card">
                                    <h4>Active Employees</h4>
                                    <div class="value">${data.total_employees_active}</div>
                                </div>
                                <div class="summary-card">
                                    <h4>Total Hours</h4>
                                    <div class="value">${data.total_hours_worked}h</div>
                                </div>
                                <div class="summary-card">
                                    <h4>Avg Hours/Employee</h4>
                                    <div class="value">${data.average_hours_per_employee}h</div>
                                </div>
                            </div>
                            
                            <div class="chart-container">
                                <h4>Employee Activity - ${data.date}</h4>
                                <table class="table">
                                    <thead>
                                        <tr>
                                            <th>Employee</th>
                                            <th>Hours Worked</th>
                                            <th>Progress</th>
                                            <th>First Activity</th>
                                            <th>Last Activity</th>
                                            <th>Heartbeats</th>
                                            <th>Logs</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${data.employees.map(emp => {
                                            const percentage = Math.min((emp.hours_worked / 8) * 100, 100);
                                            const progressColor = percentage >= 100 ? '#28a745' : percentage >= 75 ? '#ffc107' : '#dc3545';
                                            
                                            return `
                                                <tr>
                                                    <td><strong>${emp.username}</strong></td>
                                                    <td>${emp.hours_worked}h</td>
                                                    <td>
                                                        <div class="progress-bar" style="width: 100px;">
                                                            <div class="progress-fill" style="width: ${percentage}%; background: ${progressColor};"></div>
                                                            <div class="progress-text">${Math.round(percentage)}%</div>
                                                        </div>
                                                    </td>
                                                    <td>${new Date(emp.first_activity).toLocaleTimeString()}</td>
                                                    <td>${new Date(emp.last_activity).toLocaleTimeString()}</td>
                                                    <td>${emp.heartbeats_count}</td>
                                                    <td>${emp.logs_count}</td>
                                                </tr>
                                            `;
                                        }).join('')}
                                    </tbody>
                                </table>
                            </div>
                        `;
                        
                        document.getElementById('dailyReportContent').innerHTML = reportHtml;
                    }
                } catch (error) {
                    document.getElementById('dailyReportContent').innerHTML = '<p>Error loading report</p>';
                }
            }
            
            async function loadWeeklyReport() {
                const startDate = document.getElementById('weeklyDate').value;
                if (!startDate) return;
                
                try {
                    const response = await makeAuthenticatedRequest(`/api/admin/reports/weekly?start_date=${startDate}`);
                    
                    if (response && response.ok) {
                        const data = await response.json();
                        
                        let reportHtml = `
                            <div class="export-buttons">
                                <button class="btn btn-success" onclick="exportReport('weekly', '${startDate}')">📊 Export CSV</button>
                            </div>
                            
                            <div class="summary-grid">
                                <div class="summary-card">
                                    <h4>Week Range</h4>
                                    <div class="value" style="font-size: 14px;">${data.week_start} to ${data.week_end}</div>
                                </div>
                                <div class="summary-card">
                                    <h4>Total Employees</h4>
                                    <div class="value">${data.total_employees}</div>
                                </div>
                            </div>
                            
                            <div class="chart-container">
                                <h4>Weekly Employee Activity</h4>
                                <table class="table">
                                    <thead>
                                        <tr>
                                            <th>Employee</th>
                                            <th>Total Hours</th>
                                            <th>Avg Daily Hours</th>
                                            <th>Mon</th><th>Tue</th><th>Wed</th><th>Thu</th><th>Fri</th><th>Sat</th><th>Sun</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${data.employees.map(emp => `
                                            <tr>
                                                <td><strong>${emp.username}</strong></td>
                                                <td>${emp.total_hours}h</td>
                                                <td>${emp.average_daily_hours}h</td>
                                                ${emp.daily_breakdown.map(day => `<td>${day.hours_worked}h</td>`).join('')}
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                            </div>
                        `;
                        
                        document.getElementById('weeklyReportContent').innerHTML = reportHtml;
                    }
                } catch (error) {
                    document.getElementById('weeklyReportContent').innerHTML = '<p>Error loading report</p>';
                }
            }
            
            async function loadMonthlyReport() {
                const monthDate = document.getElementById('monthlyDate').value;
                if (!monthDate) return;
                
                // Convert YYYY-MM to start and end dates
                const startDate = monthDate + '-01';
                const nextMonth = new Date(monthDate + '-01');
                nextMonth.setMonth(nextMonth.getMonth() + 1);
                const endDate = nextMonth.toISOString().split('T')[0];
                
                loadCustomReport(startDate, endDate, 'monthlyReportContent');
            }
            
            async function loadCustomReport(startDate = null, endDate = null, targetElement = 'customReportContent') {
                if (!startDate) startDate = document.getElementById('customFromDate').value;
                if (!endDate) endDate = document.getElementById('customToDate').value;
                
                if (!startDate || !endDate) {
                    document.getElementById(targetElement).innerHTML = '<p>Please select both start and end dates</p>';
                    return;
                }
                
                try {
                    const response = await makeAuthenticatedRequest(`/api/admin/reports/range?start_date=${startDate}&end_date=${endDate}`);
                    
                    if (response && response.ok) {
                        const data = await response.json();
                        
                        let reportHtml = `
                            <div class="export-buttons">
                                <button class="btn btn-success" onclick="exportReport('custom', '${startDate}_${endDate}')">📊 Export CSV</button>
                            </div>
                            
                            <div class="summary-grid">
                                <div class="summary-card">
                                    <h4>Date Range</h4>
                                    <div class="value" style="font-size: 14px;">${data.start_date} to ${data.end_date}</div>
                                </div>
                                <div class="summary-card">
                                    <h4>Duration</h4>
                                    <div class="value">${data.duration_days} days</div>
                                </div>
                                <div class="summary-card">
                                    <h4>Total Heartbeats</h4>
                                    <div class="value">${data.summary.total_heartbeats}</div>
                                </div>
                                <div class="summary-card">
                                    <h4>Total Logs</h4>
                                    <div class="value">${data.summary.total_logs}</div>
                                </div>
                                <div class="summary-card">
                                    <h4>Active Employees</h4>
                                    <div class="value">${data.summary.unique_employees}</div>
                                </div>
                            </div>
                            
                            <div class="chart-container">
                                <h4>Employee Activity Summary</h4>
                                <table class="table">
                                    <thead>
                                        <tr>
                                            <th>Employee</th>
                                            <th>Estimated Active Hours</th>
                                            <th>Heartbeats</th>
                                            <th>Detailed Logs</th>
                                            <th>First Activity</th>
                                            <th>Last Activity</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${data.employees.map(emp => `
                                            <tr>
                                                <td><strong>${emp.username}</strong></td>
                                                <td>${emp.estimated_active_hours}h</td>
                                                <td>${emp.heartbeats_count}</td>
                                                <td>${emp.logs_count}</td>
                                                <td>${new Date(emp.first_activity).toLocaleString()}</td>
                                                <td>${new Date(emp.last_activity).toLocaleString()}</td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                            </div>
                        `;
                        
                        document.getElementById(targetElement).innerHTML = reportHtml;
                    }
                } catch (error) {
                    document.getElementById(targetElement).innerHTML = '<p>Error loading report</p>';
                }
            }
            
            function exportReport(type, date) {
                // Simple CSV export functionality
                let csvContent = '';
                const table = document.querySelector(`#${currentReportTab}ReportContent table`);
                
                if (table) {
                    // Get table headers
                    const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent.trim());
                    csvContent += headers.join(',') + '\n';
                    
                    // Get table rows
                    const rows = Array.from(table.querySelectorAll('tbody tr'));
                    rows.forEach(row => {
                        const cells = Array.from(row.querySelectorAll('td')).map(td => {
                            // Clean cell content (remove HTML and extra whitespace)
                            return td.textContent.trim().replace(/[,\n]/g, ' ');
                        });
                        csvContent += cells.join(',') + '\n';
                    });
                    
                    // Download CSV
                    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                    const link = document.createElement('a');
                    link.href = URL.createObjectURL(blob);
                    link.download = `employee_report_${type}_${date}.csv`;
                    link.click();
                } else {
                    alert('No report data available to export');
                }
            }
            
            async function viewEmployeeLogs(username) {
                try {
                    const response = await makeAuthenticatedRequest(`/api/admin/employees/${username}/logs?days=7`);
                    
                    if (response && response.ok) {
                        const data = await response.json();
                        const logs = data.logs || [];
                        
                        let logDetails = `<h3>📋 Logs for ${username} (Last 7 days)</h3>`;
                        logDetails += `<p><strong>Total logs:</strong> ${logs.length}</p>`;
                        
                        if (logs.length > 0) {
                            logDetails += '<div style="max-height: 400px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; margin: 10px 0;">';
                            logs.forEach(log => {
                                const logDate = new Date(log.timestamp).toLocaleString();
                                logDetails += `
                                    <div style="border-bottom: 1px solid #eee; padding: 10px 0;">
                                        <strong>📅 ${logDate}</strong><br>
                                        <strong>🖥️ Hostname:</strong> ${log.hostname}<br>
                                        <strong>🌐 Local IP:</strong> ${log.local_ip}<br>
                                        <strong>🌍 Public IP:</strong> ${log.public_ip}<br>
                                        <strong>📍 Location:</strong> ${log.location}<br>
                                        <strong>📸 Screenshot:</strong> ${log.screenshot_path ? 'Available' : 'None'}
                                    </div>
                                `;
                            });
                            logDetails += '</div>';
                        } else {
                            logDetails += '<p>No logs found for the selected period.</p>';
                        }
                        
                        showModal('Employee Logs', logDetails);
                    } else if (response === null) {
                        // Token expired, user was redirected to login
                        showModal('Session Expired', '<p>Your session has expired. Please login again.</p>');
                    } else {
                        showModal('Error', '<p>Error loading logs. Please try again.</p>');
                    }
                } catch (error) {
                    showModal('Error', '<p>Error loading logs: ' + error.message + '</p>');
                }
            }
            
            async function viewWorkingHours(username) {
                try {
                    const today = new Date().toISOString().split('T')[0];
                    const response = await makeAuthenticatedRequest(`/api/admin/employees/${username}/working-hours?date=${today}`);
                    
                    if (response && response.ok) {
                        const data = await response.json();
                        
                        let hoursDetails = `<h3>⏰ Working Hours for ${username}</h3>`;
                        hoursDetails += `<p><strong>Date:</strong> ${data.date}</p>`;
                        hoursDetails += `<p><strong>Total Hours:</strong> ${data.total_hours} hours</p>`;
                        
                        if (data.first_seen && data.last_seen) {
                            const firstSeen = new Date(data.first_seen).toLocaleTimeString();
                            const lastSeen = new Date(data.last_seen).toLocaleTimeString();
                            hoursDetails += `<p><strong>First Activity:</strong> ${firstSeen}</p>`;
                            hoursDetails += `<p><strong>Last Activity:</strong> ${lastSeen}</p>`;
                            
                            // Add visual progress bar
                            const maxHours = 8;
                            const percentage = Math.min((data.total_hours / maxHours) * 100, 100);
                            const barColor = percentage >= 100 ? '#28a745' : percentage >= 75 ? '#ffc107' : '#dc3545';
                            
                            hoursDetails += `
                                <div style="margin: 15px 0;">
                                    <div style="background: #f8f9fa; border-radius: 10px; height: 20px; position: relative;">
                                        <div style="background: ${barColor}; height: 100%; width: ${percentage}%; border-radius: 10px; transition: width 0.3s;"></div>
                                        <span style="position: absolute; top: 2px; left: 50%; transform: translateX(-50%); font-size: 12px; font-weight: bold;">
                                            ${data.total_hours}h / ${maxHours}h
                                        </span>
                                    </div>
                                </div>
                            `;
                        } else {
                            hoursDetails += '<p><em>No activity recorded for today</em></p>';
                        }
                        
                        showModal('Working Hours', hoursDetails);
                    } else if (response === null) {
                        // Token expired, user was redirected to login
                        showModal('Session Expired', '<p>Your session has expired. Please login again.</p>');
                    } else {
                        showModal('Error', '<p>Error loading working hours. Please try again.</p>');
                    }
                } catch (error) {
                    showModal('Error', '<p>Error loading working hours: ' + error.message + '</p>');
                }
            }
            
            function showModal(title, content) {
                // Create modal if it doesn't exist
                let modal = document.getElementById('customModal');
                if (!modal) {
                    modal = document.createElement('div');
                    modal.id = 'customModal';
                    modal.style.cssText = `
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        background: rgba(0,0,0,0.5);
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        z-index: 1000;
                    `;
                    
                    const modalContent = document.createElement('div');
                    modalContent.style.cssText = `
                        background: white;
                        padding: 20px;
                        border-radius: 10px;
                        max-width: 80%;
                        max-height: 80%;
                        overflow-y: auto;
                        position: relative;
                        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                    `;
                    
                    modal.appendChild(modalContent);
                    document.body.appendChild(modal);
                    
                    // Close modal when clicking outside
                    modal.addEventListener('click', (e) => {
                        if (e.target === modal) {
                            closeModal();
                        }
                    });
                }
                
                const modalContent = modal.querySelector('div');
                modalContent.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 10px;">
                        <h2 style="margin: 0; color: #333;">${title}</h2>
                        <button onclick="closeModal()" style="background: #dc3545; color: white; border: none; border-radius: 5px; padding: 5px 10px; cursor: pointer; font-size: 18px;">&times;</button>
                    </div>
                    <div>${content}</div>
                `;
                
                modal.style.display = 'flex';
            }
            
            function closeModal() {
                const modal = document.getElementById('customModal');
                if (modal) {
                    modal.style.display = 'none';
                }
            }
            
            function downloadAgent(platform) {
                if (!authToken) {
                    alert('Please login first');
                    return;
                }
                
                // Download the agent zip file
                const link = document.createElement('a');
                link.href = `/download/agent/${platform}`;
                link.download = `wfh-agent-${platform}.zip`;
                link.style.display = 'none';
                
                // Add authorization header by creating a form
                const form = document.createElement('form');
                form.method = 'GET';
                form.action = `/download/agent/${platform}`;
                form.style.display = 'none';
                
                const tokenInput = document.createElement('input');
                tokenInput.type = 'hidden';
                tokenInput.name = 'token';
                tokenInput.value = authToken;
                form.appendChild(tokenInput);
                
                document.body.appendChild(form);
                
                // Use fetch to download with proper auth
                fetch(`/download/agent/${platform}`, {
                    headers: { 'Authorization': 'Bearer ' + authToken }
                })
                .then(response => {
                    if (response.ok) {
                        return response.blob();
                    }
                    throw new Error('Download failed');
                })
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `wfh-agent-${platform}.zip`;
                    a.click();
                    window.URL.revokeObjectURL(url);
                    alert(`Agent for ${platform} downloaded successfully!`);
                })
                .catch(error => {
                    alert('Download failed: ' + error.message);
                });
            }
            
            function saveSettings() {
                showAlert('settingsAlert', 'Settings saved successfully!', 'success');
            }
            
            async function cleanupOldData() {
                if (!confirm('Are you sure you want to cleanup old data? This cannot be undone.')) {
                    return;
                }
                
                try {
                    const response = await fetch('/api/admin/cleanup', {
                        headers: { 'Authorization': 'Bearer ' + authToken }
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        showAlert('settingsAlert', 
                            `Cleanup completed: ${data.deleted_heartbeats} heartbeats, ${data.deleted_logs} logs, ${data.deleted_screenshots} screenshots deleted`, 
                            'success');
                    }
                } catch (error) {
                    showAlert('settingsAlert', 'Cleanup failed: ' + error.message, 'error');
                }
            }
            
            function showAlert(containerId, message, type) {
                const alertClass = type === 'error' ? 'alert-error' : 'alert-success';
                document.getElementById(containerId).innerHTML = 
                    `<div class="alert ${alertClass}">${message}</div>`;
                
                setTimeout(() => {
                    document.getElementById(containerId).innerHTML = '';
                }, 5000);
            }
            
            // Auto refresh dashboard data every 30 seconds
            setInterval(() => {
                if (authToken && currentSection === 'dashboard') {
                    loadDashboardData();
                }
            }, 30000);
        </script>
    </body>
    </html>
    """

# Agent download endpoints
@app.get("/download/agent/{platform}")
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
pause
"""
                zip_file.writestr('install.bat', windows_script)
                
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
    uvicorn.run(app, host="0.0.0.0", port=5000)