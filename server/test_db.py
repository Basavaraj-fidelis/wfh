
#!/usr/bin/env python3
"""
Test database connection
"""

import os
from database import engine, create_tables, SessionLocal, AdminUser
from auth import get_password_hash

def test_database():
    try:
        print("Testing database connection...")
        
        # Test connection
        with engine.connect() as conn:
            print("✓ Database connection successful")
        
        # Create tables
        create_tables()
        print("✓ Tables created/verified")
        
        # Test session
        db = SessionLocal()
        try:
            admin_count = db.query(AdminUser).count()
            print(f"✓ Database query successful - {admin_count} admin users found")
            
            # Create test admin if none exists
            if admin_count == 0:
                print("Creating test admin user...")
                hashed_password = get_password_hash("admin123")
                admin_user = AdminUser(username="admin", hashed_password=hashed_password)
                db.add(admin_user)
                db.commit()
                print("✓ Test admin user created: admin/admin123")
            
        finally:
            db.close()
        
        print("\n✓ All database tests passed!")
        
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_database()
