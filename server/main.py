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

from database import get_db, create_tables, EmployeeHeartbeat, EmployeeLog, AdminUser, EmployeeActivitySummary, EmployeeHourlyActivity
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

        # Parse and process comprehensive activity data
        try:
            activity_json = json.loads(activity_data)
            
            # Extract summary data
            date_str = activity_json.get("date", timestamp.date().isoformat())
            total_active_minutes = activity_json.get("total_active_time_minutes", 0)
            total_tracked_minutes = activity_json.get("total_tracked_time_minutes", 0)
            activity_rate = activity_json.get("activity_rate_percentage", 0)
            productivity_score = activity_json.get("summary", {}).get("productivity_score", 0)
            
            # Update or create activity summary
            existing_summary = db.query(EmployeeActivitySummary).filter(
                EmployeeActivitySummary.username == username,
                EmployeeActivitySummary.date == date_str
            ).first()
            
            if existing_summary:
                # Update existing record
                existing_summary.total_active_minutes = total_active_minutes
                existing_summary.total_tracked_minutes = total_tracked_minutes
                existing_summary.activity_rate_percentage = int(activity_rate)
                existing_summary.productivity_score = int(productivity_score)
                existing_summary.apps_used_count = activity_json.get("summary", {}).get("apps_used_count", 0)
                existing_summary.websites_visited_count = activity_json.get("summary", {}).get("websites_visited_count", 0)
                existing_summary.browser_events_count = activity_json.get("browser_events_total", 0)
                existing_summary.activitywatch_available = activity_json.get("activitywatch_available", False)
                existing_summary.app_usage_data = json.dumps(activity_json.get("our_app_usage_minutes", {}))
                existing_summary.website_usage_data = json.dumps(activity_json.get("browser_activity_counts", {}))
                existing_summary.activitywatch_data = json.dumps(activity_json.get("activitywatch_data", {}))
                existing_summary.network_location_data = json.dumps({
                    "network": activity_json.get("network_info", {}),
                    "location": activity_json.get("location_info", {})
                })
                existing_summary.updated_at = timestamp
            else:
                # Create new summary record
                activity_summary = EmployeeActivitySummary(
                    username=username,
                    date=date_str,
                    total_active_minutes=total_active_minutes,
                    total_tracked_minutes=total_tracked_minutes,
                    activity_rate_percentage=int(activity_rate),
                    productivity_score=int(productivity_score),
                    apps_used_count=activity_json.get("summary", {}).get("apps_used_count", 0),
                    websites_visited_count=activity_json.get("summary", {}).get("websites_visited_count", 0),
                    browser_events_count=activity_json.get("browser_events_total", 0),
                    activitywatch_available=activity_json.get("activitywatch_available", False),
                    app_usage_data=json.dumps(activity_json.get("our_app_usage_minutes", {})),
                    website_usage_data=json.dumps(activity_json.get("browser_activity_counts", {})),
                    activitywatch_data=json.dumps(activity_json.get("activitywatch_data", {})),
                    network_location_data=json.dumps({
                        "network": activity_json.get("network_info", {}),
                        "location": activity_json.get("location_info", {})
                    }),
                    created_at=timestamp
                )
                db.add(activity_summary)
            
            # Process hourly data if available
            keyboard_mouse_events = activity_json.get("keyboard_mouse_events", [])
            current_hour = timestamp.hour
            
            # Calculate hourly activity
            hourly_active = 0
            hourly_idle = 0
            
            for event in keyboard_mouse_events:
                try:
                    event_time = datetime.fromisoformat(event.get("timestamp", ""))
                    if event_time.hour == current_hour:
                        if event.get("is_active", False):
                            hourly_active += 1
                        else:
                            hourly_idle += 1
                except:
                    pass
            
            # Get top app and website for current hour
            app_usage = activity_json.get("our_app_usage_minutes", {})
            website_usage = activity_json.get("browser_activity_counts", {})
            
            top_app = max(app_usage.keys(), key=lambda k: app_usage[k]) if app_usage else ""
            top_website = max(website_usage.keys(), key=lambda k: website_usage[k]) if website_usage else ""
            
            # Update or create hourly record
            existing_hourly = db.query(EmployeeHourlyActivity).filter(
                EmployeeHourlyActivity.username == username,
                EmployeeHourlyActivity.date == date_str,
                EmployeeHourlyActivity.hour == current_hour
            ).first()
            
            if existing_hourly:
                existing_hourly.active_minutes = hourly_active
                existing_hourly.idle_minutes = hourly_idle
                existing_hourly.top_app = top_app
                existing_hourly.top_website = top_website
                existing_hourly.keyboard_mouse_events = len(keyboard_mouse_events)
            else:
                hourly_activity = EmployeeHourlyActivity(
                    username=username,
                    date=date_str,
                    hour=current_hour,
                    active_minutes=hourly_active,
                    idle_minutes=hourly_idle,
                    top_app=top_app,
                    top_website=top_website,
                    keyboard_mouse_events=len(keyboard_mouse_events),
                    created_at=timestamp
                )
                db.add(hourly_activity)
                
        except Exception as e:
            print(f"Error processing activity data: {e}")
            # Continue with basic log saving even if activity processing fails

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
        print(f"Log record and activity summaries saved successfully with ID: {log_record.id}")

        return {
            "status": "success",
            "message": "Comprehensive detailed log received and processed",
            "screenshot_saved": filename,
            "log_id": log_record.id,
            "activity_summary_updated": True
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
            
            # Calculate productivity based on 8 hours requirement
            # Simple formula: (actual_active_hours / 8) * 100
            productivity = min((working_hours / 8.0 * 100), 100)
        else:
            first_activity = None
            last_activity = None 
            working_hours = 0
            productivity = 0
        
        # Parse location and determine work location
        location_text = "Remote work"
        public_ip = "Unknown"
        if latest_log and latest_log.location:
            try:
                location_data = json.loads(latest_log.location)
                public_ip = location_data.get('ip', 'Unknown')
                # Check if this is the office IP
                if public_ip == "14.96.131.106":
                    location_text = "Office Bangalore"
                else:
                    location_text = "Remote work"
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
    
    # Calculate summary statistics for dashboard
    total_employees = len(enhanced_data)
    office_employees = [emp for emp in enhanced_data if emp['location'] == 'Office Bangalore']
    remote_employees = [emp for emp in enhanced_data if emp['location'] == 'Remote work']
    
    # Calculate average productivity for each location
    office_productivity = sum([emp['raw_productivity'] for emp in office_employees]) / len(office_employees) if office_employees else 0
    remote_productivity = sum([emp['raw_productivity'] for emp in remote_employees]) / len(remote_employees) if remote_employees else 0
    
    # Calculate additional hybrid work insights
    online_office = [emp for emp in office_employees if emp['status'] == 'online']
    online_remote = [emp for emp in remote_employees if emp['status'] == 'online']
    
    return {
        "employees": enhanced_data,
        "dashboard_stats": {
            "total_employees": total_employees,
            "office_count": len(office_employees),
            "remote_count": len(remote_employees),
            "office_productivity": round(office_productivity),
            "remote_productivity": round(remote_productivity),
            "online_office_count": len(online_office),
            "online_remote_count": len(online_remote),
            "hybrid_work_distribution": {
                "office_percentage": round((len(office_employees) / total_employees * 100)) if total_employees > 0 else 0,
                "remote_percentage": round((len(remote_employees) / total_employees * 100)) if total_employees > 0 else 0
            }
        }
    }

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

@app.get("/api/admin/employees/{username}/day-details")
def get_employee_day_details(
    username: str,
    date: Optional[str] = None,
    admin=Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Get comprehensive day details for a specific employee"""
    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    else:
        target_date = datetime.utcnow().date()
    
    date_str = target_date.isoformat()
    
    # Get activity summary
    activity_summary = db.query(EmployeeActivitySummary).filter(
        EmployeeActivitySummary.username == username,
        EmployeeActivitySummary.date == date_str
    ).first()
    
    # Get hourly data
    hourly_data = db.query(EmployeeHourlyActivity).filter(
        EmployeeHourlyActivity.username == username,
        EmployeeHourlyActivity.date == date_str
    ).order_by(EmployeeHourlyActivity.hour).all()
    
    # Get heartbeats for the day
    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = start_of_day + timedelta(days=1)
    
    heartbeats = db.query(EmployeeHeartbeat).filter(
        EmployeeHeartbeat.username == username,
        EmployeeHeartbeat.timestamp >= start_of_day,
        EmployeeHeartbeat.timestamp < end_of_day
    ).order_by(EmployeeHeartbeat.timestamp).all()
    
    # Get detailed logs for the day
    detailed_logs = db.query(EmployeeLog).filter(
        EmployeeLog.username == username,
        EmployeeLog.timestamp >= start_of_day,
        EmployeeLog.timestamp < end_of_day
    ).order_by(EmployeeLog.timestamp).all()
    
    # Process data for response
    if not activity_summary:
        return {
            "username": username,
            "date": date_str,
            "data_available": False,
            "message": "No comprehensive activity data available for this date"
        }
    
    # Parse comprehensive data
    try:
        app_usage = json.loads(activity_summary.app_usage_data)
        website_usage = json.loads(activity_summary.website_usage_data)
        activitywatch_data = json.loads(activity_summary.activitywatch_data)
        network_location = json.loads(activity_summary.network_location_data)
    except:
        app_usage = {}
        website_usage = {}
        activitywatch_data = {}
        network_location = {}
    
    # Format hourly breakdown
    hourly_breakdown = []
    for hour_data in hourly_data:
        hourly_breakdown.append({
            "hour": hour_data.hour,
            "active_minutes": hour_data.active_minutes,
            "idle_minutes": hour_data.idle_minutes,
            "top_app": hour_data.top_app,
            "top_website": hour_data.top_website,
            "keyboard_mouse_events": hour_data.keyboard_mouse_events,
            "screen_locked": hour_data.screen_locked
        })
    
    # Format heartbeat timeline
    heartbeat_timeline = []
    for hb in heartbeats:
        heartbeat_timeline.append({
            "timestamp": hb.timestamp,
            "status": hb.status,
            "hostname": hb.hostname
        })
    
    # Format detailed logs
    log_entries = []
    for log in detailed_logs:
        try:
            activity_data = json.loads(log.activity_data) if log.activity_data else {}
        except:
            activity_data = {}
            
        log_entries.append({
            "timestamp": log.timestamp,
            "screenshot_path": log.screenshot_path,
            "location": log.location,
            "network_info": {
                "local_ip": log.local_ip,
                "public_ip": log.public_ip
            },
            "activity_summary": activity_data.get("summary", {}),
            "apps_tracked": len(activity_data.get("our_app_usage_minutes", {})),
            "websites_tracked": len(activity_data.get("browser_activity_counts", {}))
        })
    
    return {
        "username": username,
        "date": date_str,
        "data_available": True,
        "summary": {
            "total_active_minutes": activity_summary.total_active_minutes,
            "total_tracked_minutes": activity_summary.total_tracked_minutes,
            "activity_rate_percentage": activity_summary.activity_rate_percentage,
            "productivity_score": activity_summary.productivity_score,
            "apps_used_count": activity_summary.apps_used_count,
            "websites_visited_count": activity_summary.websites_visited_count,
            "activitywatch_available": activity_summary.activitywatch_available
        },
        "app_usage": app_usage,
        "website_usage": website_usage,
        "activitywatch_data": activitywatch_data,
        "network_location": network_location,
        "hourly_breakdown": hourly_breakdown,
        "heartbeat_timeline": heartbeat_timeline,
        "detailed_logs": log_entries,
        "work_location": "Office" if network_location.get("network", {}).get("public_ip") == "14.96.131.106" else "Remote"
    }

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
    """Get comprehensive daily activity report for all employees"""
    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    else:
        target_date = datetime.utcnow().date()

    date_str = target_date.isoformat()

    # Get activity summaries for the date
    activity_summaries = db.query(EmployeeActivitySummary).filter(
        EmployeeActivitySummary.date == date_str
    ).all()

    # Get hourly data for the date
    hourly_data = db.query(EmployeeHourlyActivity).filter(
        EmployeeHourlyActivity.date == date_str
    ).all()

    # Process comprehensive report
    report_data = []
    total_productivity = 0
    total_active_time = 0
    activitywatch_users = 0

    for summary in activity_summaries:
        # Get user's hourly breakdown
        user_hourly = [h for h in hourly_data if h.username == summary.username]
        hourly_breakdown = {}
        for hour_data in user_hourly:
            hourly_breakdown[hour_data.hour] = {
                "active_minutes": hour_data.active_minutes,
                "idle_minutes": hour_data.idle_minutes,
                "top_app": hour_data.top_app,
                "top_website": hour_data.top_website,
                "events_count": hour_data.keyboard_mouse_events
            }

        # Parse app and website usage
        try:
            app_usage = json.loads(summary.app_usage_data)
            website_usage = json.loads(summary.website_usage_data)
            activitywatch_data = json.loads(summary.activitywatch_data)
            network_location = json.loads(summary.network_location_data)
        except:
            app_usage = {}
            website_usage = {}
            activitywatch_data = {}
            network_location = {}

        if summary.activitywatch_available:
            activitywatch_users += 1

        total_productivity += summary.productivity_score
        total_active_time += summary.total_active_minutes

        report_data.append({
            "username": summary.username,
            "date": summary.date,
            "total_active_minutes": summary.total_active_minutes,
            "total_tracked_minutes": summary.total_tracked_minutes,
            "activity_rate_percentage": summary.activity_rate_percentage,
            "productivity_score": summary.productivity_score,
            "apps_used_count": summary.apps_used_count,
            "websites_visited_count": summary.websites_visited_count,
            "browser_events_count": summary.browser_events_count,
            "activitywatch_available": summary.activitywatch_available,
            "app_usage": app_usage,
            "website_usage": website_usage,
            "activitywatch_data": activitywatch_data,
            "network_location": network_location,
            "hourly_breakdown": hourly_breakdown
        })

    # Calculate aggregate statistics
    avg_productivity = (total_productivity / len(activity_summaries)) if activity_summaries else 0
    total_employees = len(activity_summaries)

    return {
        "date": date_str,
        "total_employees_active": total_employees,
        "average_productivity_score": round(avg_productivity, 2),
        "total_active_time_minutes": total_active_time,
        "activitywatch_integration_rate": round((activitywatch_users / total_employees * 100), 2) if total_employees > 0 else 0,
        "comprehensive_data_available": True,
        "employees": report_data
    }

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
            
            # Calculate active time (sum of gaps <= 15 minutes)
            active_seconds = 0
            for i in range(len(heartbeats) - 1):
                gap = (heartbeats[i + 1].timestamp - heartbeats[i].timestamp).total_seconds()
                if gap <= 900:  # 15 minutes
                    active_seconds += gap
            
            active_hours = active_seconds / 3600
            total_span_hours = (last_heartbeat - first_heartbeat).total_seconds() / 3600
            
            # Calculate productivity based on 8 hours requirement
            # Simple formula: (actual_active_hours / 8) * 100
            productivity = min((active_hours / 8.0 * 100), 100)
            
            total_hours += active_hours

            # Get detailed logs count
            logs_count = db.query(EmployeeLog).filter(
                EmployeeLog.username == username,
                EmployeeLog.timestamp >= start_of_day,
                EmployeeLog.timestamp < end_of_day
            ).count()

            report_data.append({
                "username": username,
                "hours_worked": round(active_hours, 2),
                "total_span_hours": round(total_span_hours, 2),
                "productivity": f"{int(productivity)}%",
                "first_activity": first_heartbeat,
                "last_activity": last_heartbeat,
                "heartbeats_count": len(heartbeats),
                "logs_count": logs_count
            })

    # Calculate work location statistics for the day
    office_employees_today = []
    remote_employees_today = []
    
    for employee_data in report_data:
        # Get employee's location for this date
        latest_log_for_date = db.query(EmployeeLog).filter(
            EmployeeLog.username == employee_data["username"],
            EmployeeLog.timestamp >= start_of_day,
            EmployeeLog.timestamp < end_of_day
        ).order_by(desc(EmployeeLog.timestamp)).first()
        
        if latest_log_for_date and latest_log_for_date.location:
            try:
                location_data = json.loads(latest_log_for_date.location)
                public_ip = location_data.get('ip', 'Unknown')
                if public_ip == "14.96.131.106":
                    office_employees_today.append(employee_data)
                    employee_data["work_location"] = "Office Bangalore"
                else:
                    remote_employees_today.append(employee_data)
                    employee_data["work_location"] = "Remote Work"
            except:
                remote_employees_today.append(employee_data)
                employee_data["work_location"] = "Remote Work"
        else:
            remote_employees_today.append(employee_data)
            employee_data["work_location"] = "Remote Work"
    
    office_hours = sum([emp["hours_worked"] for emp in office_employees_today])
    remote_hours = sum([emp["hours_worked"] for emp in remote_employees_today])
    
    return {
        "date": target_date.isoformat(),
        "total_employees_active": len(report_data),
        "total_hours_worked": round(total_hours, 2),
        "average_hours_per_employee": round(total_hours / len(report_data), 2) if report_data else 0,
        "work_location_breakdown": {
            "office_employees": len(office_employees_today),
            "remote_employees": len(remote_employees_today),
            "office_hours_total": round(office_hours, 2),
            "remote_hours_total": round(remote_hours, 2),
            "office_percentage": round((len(office_employees_today) / len(report_data) * 100)) if report_data else 0
        },
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

# Screenshot serving endpoint
@app.get("/api/screenshots/{filename}")
def serve_screenshot(filename: str):
    """Serve screenshot files"""
    try:
        screenshot_path = os.path.join(screenshots_dir, filename)
        if os.path.exists(screenshot_path):
            from fastapi.responses import FileResponse
            return FileResponse(screenshot_path, media_type="image/png")
        else:
            raise HTTPException(status_code=404, detail="Screenshot not found")
    except Exception as e:
        print(f"Error serving screenshot {filename}: {e}")
        raise HTTPException(status_code=500, detail="Error serving screenshot")

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