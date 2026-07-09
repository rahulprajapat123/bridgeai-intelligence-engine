"""Drop all tables and recreate them."""
from sqlalchemy import text
from research_intel.db import engine
from research_intel.models import Base

print("WARNING: Dropping all tables with CASCADE...")
with engine.connect() as conn:
    conn.execute(text("DROP SCHEMA public CASCADE"))
    conn.execute(text("CREATE SCHEMA public"))
    conn.commit()

print("Recreating all tables...")
Base.metadata.create_all(engine)
print("Database reset complete!")
