#!/usr/bin/env python3
"""Test Neon database connection locally."""

import os
import sys

# Your Neon database URL
DATABASE_URL = "postgresql://checking_owner:npg_MdnKY0Gh1amc@ep-super-scene-a51ij7h2-pooler.us-east-2.aws.neon.tech/checking?sslmode=require&channel_binding=require"

def test_neon_connection():
    """Test connection to Neon database."""
    print("🧪 Testing Neon PostgreSQL connection...")
    
    try:
        import psycopg2
        import psycopg2.extras
        print("✅ psycopg2 imported successfully")
    except ImportError as e:
        print(f"❌ psycopg2 import failed: {e}")
        print("💡 Install with: pip install psycopg2-binary")
        return False
    
    try:
        print(f"🔗 Connecting to: {DATABASE_URL[:50]}...")
        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        print("✅ Connection successful!")
        
        # Test basic query
        with conn.cursor() as cur:
            cur.execute("SELECT version() as pg_version")
            version = cur.fetchone()
            print(f"✅ Database version: {version['pg_version'][:50]}...")
        
        # Test table creation
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)
            print("✅ Table creation test successful")
        
        conn.commit()
        conn.close()
        print("✅ All Neon database tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Neon connection failed: {e}")
        import traceback
        print(f"❌ Full error: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = test_neon_connection()
    if not success:
        sys.exit(1)