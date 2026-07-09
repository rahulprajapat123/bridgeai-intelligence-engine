#!/usr/bin/env python
"""Test database connection and performance."""

import time
from research_intel.db import SessionLocal
from sqlalchemy import text

print("🔍 Testing database connection...")

# Test basic connectivity
try:
    session = SessionLocal()
    result = session.execute(text("SELECT 1"))
    print("✅ Database connection successful")
    session.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")
    exit(1)

# Test query performance
try:
    session = SessionLocal()
    start = time.time()
    result = session.execute(text("SELECT COUNT(*) FROM research_items"))
    count = result.scalar()
    elapsed = time.time() - start
    print(f"✅ Query test passed: {count} items ({elapsed:.2f}s)")
    session.close()
except Exception as e:
    print(f"❌ Query failed: {e}")
    exit(1)

# Test connection timeout handling
try:
    session = SessionLocal()
    print("⏳ Testing connection resilience (15 second idle)...")
    time.sleep(15)
    result = session.execute(text("SELECT 1"))
    print("✅ Connection stayed alive after idle period")
    session.close()
except Exception as e:
    print(f"⚠️  Connection dropped after idle: {e}")
    print("   This is expected for free tier databases")

print("\n✅ All database tests completed")
