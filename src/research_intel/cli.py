from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from research_intel.config import get_settings
from research_intel.db import SessionLocal, init_db
from research_intel.schemas import ProjectContextInput
from research_intel.services.factory import build_services


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="research-intel")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Create database tables.")
    sub.add_parser("reset-db", help="Drop all tables and recreate them (WARNING: destroys all data).")

    analyze = sub.add_parser("analyze-brief", help="Analyze a brief from a file.")
    analyze.add_argument("file", type=Path)

    ingest = sub.add_parser("ingest", help="Run ingestion for one topic.")
    ingest.add_argument("topic")
    ingest.add_argument("--domain")
    ingest.add_argument("--max-per-source", type=int, default=10)
    ingest.add_argument("--dry-run", action="store_true")

    recommend = sub.add_parser("recommend", help="Generate a recommendation from a JSON context file.")
    recommend.add_argument("file", type=Path)
    recommend.add_argument("--top-k", type=int, default=12)
    recommend.add_argument("--min-credibility", type=float, default=60)

    args = parser.parse_args(argv)
    settings = get_settings()
    services = build_services(settings)
    init_db()

    if args.command == "init-db":
        print("Database initialized.")
        return 0
    if args.command == "reset-db":
        from research_intel.db import engine
        from research_intel.models import Base
        print("WARNING: Dropping all tables...")
        Base.metadata.drop_all(engine)
        print("Recreating all tables...")
        Base.metadata.create_all(engine)
        print("Database reset complete.")
        return 0
    if args.command == "analyze-brief":
        text = args.file.read_text(encoding="utf-8")
        print(services.brief.analyze(text).model_dump_json(indent=2))
        return 0
    if args.command == "ingest":
        session = SessionLocal()
        try:
            result = asyncio.run(
                services.ingestion.ingest_topic(
                    session,
                    topic=args.topic,
                    domain=args.domain,
                    max_per_source=args.max_per_source,
                    dry_run=args.dry_run,
                )
            )
            print(result.model_dump_json(indent=2))
            return 0
        finally:
            session.close()
    if args.command == "recommend":
        payload = json.loads(args.file.read_text(encoding="utf-8"))
        context = ProjectContextInput(**payload.get("project_context", payload))
        session = SessionLocal()
        try:
            result = services.recommendation.recommend(
                session,
                context,
                top_k=args.top_k,
                min_credibility=args.min_credibility,
            )
            print(result.model_dump_json(indent=2))
            return 0
        finally:
            session.close()
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
