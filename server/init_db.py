
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import create_tables, get_db, AdminUser
from auth import get_password_hash

def initialize_database():
    """Initialize database with proper schema and default admin user"""
    try:
        print("Initializing database...")
        
        # Create all tables with proper schema
        create_tables()
        print("Database tables created/updated successfully")
        
        # Create default admin user if none exists
        db = next(get_db())
        try:
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
        finally:
            db.close()
            
        print("Database initialization completed successfully")
        
    except Exception as e:
        print(f"Database initialization error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    initialize_database()
