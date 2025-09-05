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
                    <div id="employeesList">Loading employees...</div>
                </div>
                
                <!-- Agent Download Section -->
                <div id="agentSection" class="content-section">
                    <h3>Agent Download & Setup</h3>
                    <p>Download the monitoring agent to install on employee computers.</p>
                    
                    <div class="download-card">
                        <h4>Windows Agent</h4>
                        <p>For Windows 7/8/10/11 systems</p>
                        <button class="btn btn-primary-sm" onclick="downloadAgent('windows')">Download Windows Agent</button>
                    </div>
                    
                    <div class="download-card">
                        <h4>macOS Agent</h4>
                        <p>For macOS 10.12 and newer</p>
                        <button class="btn btn-primary-sm" onclick="downloadAgent('mac')">Download macOS Agent</button>
                    </div>
                    
                    <div class="download-card">
                        <h4>Linux Agent</h4>
                        <p>For Ubuntu, CentOS, and other Linux distributions</p>
                        <button class="btn btn-primary-sm" onclick="downloadAgent('linux')">Download Linux Agent</button>
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
            
            // Check if already logged in
            if (authToken) {
                showDashboard();
                loadDashboardData();
            }
            
            async function login(event) {
                event.preventDefault();
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
                        localStorage.setItem('adminToken', authToken);
                        showDashboard();
                        loadDashboardData();
                    } else {
                        showAlert('loginAlert', 'Invalid username or password', 'error');
                    }
                } catch (error) {
                    showAlert('loginAlert', 'Connection error: ' + error.message, 'error');
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
                }
            }
            
            async function loadDashboardData() {
                try {
                    const response = await fetch('/api/admin/employees/status', {
                        headers: { 'Authorization': 'Bearer ' + authToken }
                    });
                    
                    if (response.ok) {
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
                    }
                } catch (error) {
                    console.error('Failed to load dashboard data:', error);
                }
            }
            
            async function loadEmployees() {
                try {
                    const response = await fetch('/api/admin/employees/status', {
                        headers: { 'Authorization': 'Bearer ' + authToken }
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        const employees = data.employees || [];
                        
                        const tableHtml = `
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>Employee</th>
                                        <th>Hostname</th>
                                        <th>Status</th>
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
                } catch (error) {
                    document.getElementById('employeesList').innerHTML = '<p>Error loading employees</p>';
                }
            }
            
            function refreshEmployees() {
                loadEmployees();
            }
            
            async function viewEmployeeLogs(username) {
                try {
                    const response = await fetch(`/api/admin/employees/${username}/logs?days=7`, {
                        headers: { 'Authorization': 'Bearer ' + authToken }
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        alert(`${username} has ${data.logs.length} logs in the last 7 days`);
                    }
                } catch (error) {
                    alert('Error loading logs');
                }
            }
            
            async function viewWorkingHours(username) {
                try {
                    const response = await fetch(`/api/admin/employees/${username}/working-hours`, {
                        headers: { 'Authorization': 'Bearer ' + authToken }
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        alert(`${username} worked ${data.total_hours} hours today (${data.date})`);
                    }
                } catch (error) {
                    alert('Error loading working hours');
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
    """Download agent for specified platform"""
    import zipfile
    import io
    
    if platform not in ['windows', 'mac', 'linux']:
        raise HTTPException(status_code=400, detail="Invalid platform")
    
    # Create agent zip file in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add main agent file
        with open('../agent/agent.py', 'r') as f:
            agent_content = f.read()
        zip_file.writestr('agent.py', agent_content)
        
        # Add requirements
        with open('../agent/agent_requirements.txt', 'r') as f:
            requirements_content = f.read()
        zip_file.writestr('agent_requirements.txt', requirements_content)
        
        # Add platform-specific instructions
        instructions = f"""
# WFH Monitoring Agent Setup - {platform.title()}

## Installation Instructions

1. Ensure Python 3.7+ is installed on this machine
2. Extract these files to a directory (e.g., C:\\wfh-agent\\ on Windows)
3. Open command prompt/terminal in that directory
4. Run: pip install -r agent_requirements.txt
5. Edit agent.py to set your server URL (line 166)
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
        elif platform == 'mac':
            instructions += """
### macOS Setup:  
- May need to allow Python in Privacy & Security settings
- For startup: Create LaunchAgent plist file in ~/Library/LaunchAgents/
- Grant screen recording permissions in System Preferences
"""
        elif platform == 'linux':
            instructions += """
### Linux Setup:
- Install python3-pip if not available: sudo apt install python3-pip
- For startup: Create systemd service or add to ~/.profile
- May need to install python3-tk for screenshot functionality
"""
        
        zip_file.writestr('README.txt', instructions)
    
    zip_buffer.seek(0)
    
    return StreamingResponse(
        io.BytesIO(zip_buffer.read()),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=wfh-agent-{platform}.zip"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)