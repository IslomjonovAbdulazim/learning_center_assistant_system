#!/usr/bin/env python3
"""
Reset database script - drops and recreates all tables
"""

from app.database import reset_database, SessionLocal
from app.models import User
from app.auth import get_password_hash


def main():
    print("🔄 Resetting database...")

    # Reset database
    reset_database()
    print("✅ Database tables recreated")

    # Create admin user
    db = SessionLocal()
    try:
        admin_user = User(
            fullname="Admin",
            phone="+998990330919",
            password=get_password_hash("aisha"),
            role="admin"
        )
        db.add(admin_user)
        db.commit()
        print("✅ Admin user created: +998990330919 / aisha")
    except Exception as e:
        print(f"❌ Error creating admin: {e}")
    finally:
        db.close()

    print("🎉 Database reset complete!")


if __name__ == "__main__":
    main()