#!/usr/bin/env python3
"""
Database Initialization Script for S.C.O.U.T
Run this script to create the necessary database tables
"""

import sys
from src.db import Database

def initialize_database():
    """Initialize the database by creating all tables"""
    print("🔧 Initializing S.C.O.U.T Database...")
    
    try:
        db = Database()
        if db.connect():
            db.initialize_database()
            print("✅ Database tables created successfully!")
            db.disconnect()
            return True
        else:
            print("❌ Failed to connect to database")
            return False
            
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        return False

def test_database_connection():
    """Test database connection"""
    print("🔌 Testing database connection...")
    
    try:
        db = Database()
        if db.connect():
            print("✅ Database connection successful!")
            db.disconnect()
            return True
        else:
            print("❌ Database connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

if __name__ == "__main__":
    print("S.C.O.U.T Database Setup")
    print("=" * 40)
    
    # Test connection first
    if not test_database_connection():
        print("\nPlease check your database configuration in config.json")
        print("Make sure MySQL is running and credentials are correct")
        sys.exit(1)
    
    # Initialize database
    print("\n" + "=" * 40)
    if initialize_database():
        print("\n🎉 Database setup completed successfully!")
        print("\nNext steps:")
        print("1. Run: python main.py (to start monitoring)")
    else:
        print("\n❌ Database setup failed")
        sys.exit(1)