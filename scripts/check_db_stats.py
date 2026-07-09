#!/usr/bin/env python
"""Check database statistics for research items."""

from research_intel.db import SessionLocal
from research_intel.models import ResearchItem

session = SessionLocal()

total = session.query(ResearchItem).count()
academic = session.query(ResearchItem).filter_by(source_type="academic").count()
code = session.query(ResearchItem).filter_by(source_type="code").count()
news = session.query(ResearchItem).filter_by(source_type="news").count()
industry = session.query(ResearchItem).filter_by(source_type="industry").count()
blog = session.query(ResearchItem).filter_by(source_type="blog").count()
web = session.query(ResearchItem).filter_by(source_type="web").count()

print(f"=== Database Research Items ===")
print(f"Total items: {total}")
print(f"Academic (papers): {academic}")
print(f"Code (GitHub): {code}")
print(f"News: {news}")
print(f"Industry: {industry}")
print(f"Blog: {blog}")
print(f"Web: {web}")

session.close()
