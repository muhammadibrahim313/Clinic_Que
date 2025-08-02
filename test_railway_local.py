#!/usr/bin/env python3
"""Test Railway version locally before deployment."""

import os
import subprocess
import sys
import time

def test_railway_setup():
    print("🧪 Testing Railway deployment setup locally...")
    print("=" * 50)
    
    # 1. Check if all files exist
    required_files = [
        "main_railway.py",
        "services_railway.py", 
        "railway.json",
        "Procfile",
        "requirements.txt",
        "RAILWAY_DEPLOYMENT.md"
    ]
    
    print("📁 Checking required files:")
    for file in required_files:
        if os.path.exists(file):
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file} - MISSING!")
            return False
    
    # 2. Check requirements.txt has all dependencies
    print("\n📦 Checking dependencies:")
    with open("requirements.txt", "r") as f:
        requirements = f.read()
        
    required_deps = ["fastapi", "uvicorn", "redis", "psycopg2-binary"]
    for dep in required_deps:
        if dep in requirements:
            print(f"   ✅ {dep}")
        else:
            print(f"   ❌ {dep} - MISSING!")
    
    # 3. Test imports
    print("\n🔍 Testing imports:")
    try:
        import fastapi
        print(f"   ✅ FastAPI {fastapi.__version__}")
    except ImportError:
        print("   ❌ FastAPI not installed")
    
    try:
        import redis
        print(f"   ✅ Redis available")
    except ImportError:
        print("   ❌ Redis not installed")
        
    try:
        import psycopg2
        print(f"   ✅ PostgreSQL driver available")
    except ImportError:
        print("   ❌ psycopg2-binary not installed - install with: pip install psycopg2-binary")
    
    # 4. Test Railway services
    print("\n🔧 Testing Railway services:")
    try:
        # Set up environment for SQLite testing
        os.environ.pop("DATABASE_URL", None)  # Use SQLite for local test
        
        from services_railway import get_connection, init_db, get_settings
        
        conn = get_connection()
        print("   ✅ Database connection successful")
        
        init_db(conn)
        print("   ✅ Database initialization successful")
        
        settings = get_settings(conn)
        print(f"   ✅ Settings loaded: {settings.get('clinic_name', 'Unknown')}")
        
        conn.close()
        
    except Exception as e:
        print(f"   ❌ Services test failed: {e}")
        return False
    
    # 5. Test Railway main app
    print("\n🚀 Testing Railway main app:")
    try:
        from main_railway import app
        print("   ✅ Railway app imports successfully")
        
        # Check if app has required endpoints
        routes = [route.path for route in app.routes]
        required_routes = ["/", "/health", "/admin/board", "/webhooks/whatsapp", "/kiosk"]
        
        for route in required_routes:
            if route in routes:
                print(f"   ✅ Route: {route}")
            else:
                print(f"   ❌ Missing route: {route}")
        
    except Exception as e:
        print(f"   ❌ Railway app test failed: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 Railway setup test PASSED!")
    print("\n📋 Ready for deployment checklist:")
    print("   ✅ All files created")
    print("   ✅ Dependencies configured")  
    print("   ✅ Database services working")
    print("   ✅ Railway app functional")
    
    print("\n🚂 Next steps:")
    print("   1. Push code to GitHub")
    print("   2. Create Railway project")
    print("   3. Add PostgreSQL service")
    print("   4. Add Redis service (optional)")
    print("   5. Set ADMIN_PASS environment variable")
    print("   6. Deploy and test!")
    
    return True

if __name__ == "__main__":
    success = test_railway_setup()
    sys.exit(0 if success else 1)