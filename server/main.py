import os
import json
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse
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
    create_tables()
    # Create default admin user if none exists
    db = next(get_db())
    admin = db.query(AdminUser).filter(AdminUser.username == "admin").first()
    if not admin:
        hashed_password = get_password_hash("admin123")
        admin_user = AdminUser(username="admin", hashed_password=hashed_password)
        db.add(admin_user)
        db.commit()
        print("Default admin user created: admin/admin123")
    db.close()

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
    # Save screenshot
    timestamp = datetime.utcnow()
    filename = f"{username}_{timestamp.strftime('%Y%m%d_%H%M%S')}.png"
    screenshot_path = os.path.join(screenshots_dir, filename)
    
    with open(screenshot_path, "wb") as buffer:
        content = screenshot.file.read()
        buffer.write(content)
    
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
    db.add(log_record)
    db.commit()
    
    return {"status": "success", "message": "Detailed log received", "screenshot_saved": filename}

# Admin authentication
@app.post("/api/admin/login")
def admin_login(login_data: AdminLogin, db: Session = Depends(get_db)):
    """Admin login endpoint"""
    admin = db.query(AdminUser).filter(AdminUser.username == login_data.username).first()
    if not admin or not verify_password(login_data.password, admin.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": admin.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Admin dashboard endpoints
@app.get("/api/admin/employees/status")
def get_employee_status(admin=Depends(verify_admin_token), db: Session = Depends(get_db)):
    """Get current online status of all employees"""
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
        employees.append({
            "username": heartbeat.username,
            "hostname": heartbeat.hostname,
            "status": "online" if is_online else "offline",
            "last_seen": heartbeat.timestamp,
            "last_heartbeat": heartbeat.timestamp
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

# Basic dashboard HTML (simple admin interface)
@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>WFH Employee Monitoring - Admin Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { text-align: center; margin-bottom: 40px; }
            .section { margin: 30px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }
            .employee { padding: 10px; border-bottom: 1px solid #eee; }
            .online { color: green; font-weight: bold; }
            .offline { color: red; font-weight: bold; }
            button { padding: 10px 20px; margin: 10px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background: #0056b3; }
            input { padding: 8px; margin: 5px; }
            .login-form { max-width: 400px; margin: 0 auto; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>WFH Employee Monitoring System</h1>
                <p>Admin Dashboard</p>
            </div>
            
            <div class="section">
                <h2>Admin Login</h2>
                <div class="login-form">
                    <input type="text" id="username" placeholder="Username" value="admin">
                    <input type="password" id="password" placeholder="Password" value="admin123">
                    <button onclick="login()">Login</button>
                </div>
            </div>
            
            <div class="section">
                <h2>API Endpoints</h2>
                <p><strong>Agent Token:</strong> agent-secret-token-change-this-in-production</p>
                <ul>
                    <li>POST /api/heartbeat - Agent heartbeat endpoint</li>
                    <li>POST /api/log - Agent detailed log endpoint</li>
                    <li>POST /api/admin/login - Admin login</li>
                    <li>GET /api/admin/employees/status - Employee status</li>
                    <li>GET /api/admin/employees/{username}/logs - Employee logs</li>
                    <li>GET /api/admin/employees/{username}/working-hours - Working hours calculation</li>
                </ul>
            </div>
            
            <div class="section">
                <h2>Quick Actions</h2>
                <button onclick="getEmployeeStatus()">Get Employee Status</button>
                <button onclick="cleanupOldData()">Cleanup Old Data</button>
                <div id="results"></div>
            </div>
        </div>
        
        <script>
            let authToken = '';
            
            async function login() {
                const username = document.getElementById('username').value;
                const password = document.getElementById('password').value;
                
                try {
                    const response = await fetch('/api/admin/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ username, password })
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        authToken = data.access_token;
                        alert('Login successful!');
                    } else {
                        alert('Login failed!');
                    }
                } catch (error) {
                    alert('Error: ' + error.message);
                }
            }
            
            async function getEmployeeStatus() {
                if (!authToken) {
                    alert('Please login first');
                    return;
                }
                
                try {
                    const response = await fetch('/api/admin/employees/status', {
                        headers: { 'Authorization': 'Bearer ' + authToken }
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        document.getElementById('results').innerHTML = 
                            '<h3>Employee Status:</h3><pre>' + JSON.stringify(data, null, 2) + '</pre>';
                    } else {
                        alert('Failed to get employee status');
                    }
                } catch (error) {
                    alert('Error: ' + error.message);
                }
            }
            
            async function cleanupOldData() {
                if (!authToken) {
                    alert('Please login first');
                    return;
                }
                
                try {
                    const response = await fetch('/api/admin/cleanup', {
                        headers: { 'Authorization': 'Bearer ' + authToken }
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        document.getElementById('results').innerHTML = 
                            '<h3>Cleanup Results:</h3><pre>' + JSON.stringify(data, null, 2) + '</pre>';
                    } else {
                        alert('Failed to cleanup data');
                    }
                } catch (error) {
                    alert('Error: ' + error.message);
                }
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)