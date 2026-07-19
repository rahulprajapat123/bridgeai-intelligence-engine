"""Approve a Daily Intelligence batch, filter it, and save its PDF export."""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from research_intel.api.daily_routes import BulkReview, bulk_review, submit
from research_intel.api.signal_filter_routes import (
    BatchFilterRequest,
    export_filtered_pdf,
    filter_batch,
)
from research_intel.db import SessionLocal
from research_intel.models import DailySummary, IngestionBatch


async def main(batch_id: str, output_dir: Path) -> None:
    session = SessionLocal()
    try:
        batch = session.get(IngestionBatch, batch_id)
        if not batch.review_locked:
            summary_ids = [
                row.id for row in session.query(DailySummary).filter_by(
                    batch_id=batch_id, summary_level="item"
                )
            ]
            if summary_ids:
                bulk_review(BulkReview(summary_ids=summary_ids, action="approve"), session, "codex-e2e")
            submit(batch_id, session, "codex-e2e")
    finally:
        session.close()

    result = await filter_batch(BatchFilterRequest(
        batch_id=batch_id,
        novelty_threshold=0,
        relevance_threshold=0,
        max_items=500,
        enable_clustering=True,
        enable_qa=True,
    ))
    if not result["filtered_items"]:
        from research_intel.api.signal_filter_routes import ReviewRequest, get_run, review
        run = get_run(result["run_id"])
        review_items = [item for item in run.items if item.status == "review"]
        if review_items:
            review(result["run_id"], ReviewRequest(
                item_id=review_items[0].item_id,
                decision="accepted",
                notes="Accepted for end-to-end export verification.",
            ))
            result["summary"]["output_items"] = 1
            result["filtered_items"] = [{"item_id": review_items[0].item_id}]
        else:
            counts: dict[str, int] = {}
            for item in run.items:
                counts[item.status] = counts.get(item.status, 0) + 1
            reasons: dict[str, int] = {}
            for decision in run.decisions:
                reasons[decision.reason_code] = reasons.get(decision.reason_code, 0) + 1
            failures = [
                (d.item_id, d.reason_code, d.explanation, d.threshold, d.observed_value)
                for d in run.decisions if d.decision in {"reject", "review"}
            ][:10]
            raise RuntimeError(f"Filter produced no accepted or review items; statuses={counts}; reasons={reasons}; failures={failures}")
    response = await export_filtered_pdf(result["run_id"])
    pdf = b"".join([chunk async for chunk in response.body_iterator])
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"BridgeAI_Filtered_Signals_{result['run_id'][:8]}.pdf"
    target.write_bytes(pdf)
    print({"batch_id": batch_id, "run_id": result["run_id"], **result["summary"], "pdf": str(target), "pdf_bytes": len(pdf)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("batch_id")
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    args = parser.parse_args()
    asyncio.run(main(args.batch_id, args.output_dir))
