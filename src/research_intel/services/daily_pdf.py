from __future__ import annotations

from io import BytesIO
from datetime import UTC, datetime
from xml.sax.saxutils import escape, quoteattr
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus.tableofcontents import TableOfContents
from research_intel.models import DailyIntelligenceReport, DailyRawItem, DailySourceRun, DailySummary, IngestionBatch

SOURCE_TYPES = ("academic", "code", "news", "blog", "web", "social")

class NumberedDocTemplate(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in {"Section", "Source"}:
            level = 0 if flowable.style.name == "Section" else 1
            key = f"toc-{self.page}-{flowable.getPlainText()}"
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (level, flowable.getPlainText(), self.page, key))

def build_daily_pdf(session, batch: IngestionBatch, include_pending=False, include_rejected=False) -> bytes:
    buffer = BytesIO(); styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Brand", parent=styles["Title"], textColor=colors.HexColor("#194B57"), alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading1"], textColor=colors.HexColor("#194B57"), spaceBefore=12))
    styles.add(ParagraphStyle(name="Source", parent=styles["Heading2"], textColor=colors.HexColor("#C06B3E")))
    doc = NumberedDocTemplate(buffer, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm, title=f"BridgeAI Daily Intelligence {batch.id}")
    # An unlocked/in-progress batch has only pending items. Export those so the PDF
    # reflects retrieved data; locked batches remain approved/edited-only by default.
    include_pending = include_pending or not batch.review_locked
    statuses = ["approved", "edited"] + (["pending"] if include_pending else []) + (["rejected"] if include_rejected else [])
    eligible_count = session.query(DailyRawItem).filter(DailyRawItem.batch_id == batch.id, DailyRawItem.duplicate_of.is_(None), DailyRawItem.review_status.in_(statuses)).count()
    story = [Paragraph("BridgeAI Daily Intelligence", styles["Brand"]), Spacer(1, 6*mm), Paragraph(f"Batch date: {(batch.started_at or batch.created_at).date()}<br/>Batch ID: {batch.id}<br/>Status: {batch.status}<br/>Items included: {eligible_count}", styles["BodyText"]), Spacer(1, 8*mm)]
    if eligible_count:
        story.extend([Paragraph("Table of Contents", styles["Heading1"]), TableOfContents(), PageBreak()])
    else:
        story.append(Paragraph("No persisted items are available yet. Wait for at least one source to complete, then export again.", styles["BodyText"]))
    
    items_without_summary = 0
    for source_type in SOURCE_TYPES:
        items = session.query(DailyRawItem).filter(DailyRawItem.batch_id == batch.id, DailyRawItem.source_type == source_type, DailyRawItem.duplicate_of.is_(None), DailyRawItem.review_status.in_(statuses)).order_by(DailyRawItem.source_name, DailyRawItem.published_at.desc()).all()
        if not items: continue
        story.append(Paragraph(source_type.title(), styles["Section"])); current_source = None
        for item in items:
            source_heading = None
            if item.source_name != current_source:
                current_source = item.source_name; source_heading = Paragraph(current_source, styles["Source"])
            summary = session.query(DailySummary).filter_by(item_id=item.id, summary_level="item").first()
            if not summary:
                # Create placeholder summary for items without AI summarization yet
                items_without_summary += 1
                displayed = (item.cleaned_content or item.raw_content or item.title)[:500]
                findings = []
                relevance = "Awaiting AI summarization"
            else:
                displayed = summary.edited_summary_text or summary.summary_text
                label = "Human-edited" if summary.edited_summary_text else "AI-generated"
                findings = summary.structured_summary_json.get("key_findings", [])
                relevance = summary.structured_summary_json.get("business_relevance", "")
            
            rows = [[Paragraph(escape(item.title or "Untitled"), styles["Heading3"])], [Paragraph(f"Source: {escape(item.source_name)} | Published: {item.published_at.date() if item.published_at else 'Unknown'} | Review: {escape(item.review_status)}", styles["BodyText"])], [Paragraph(escape(displayed or "No content available."), styles["BodyText"])]]
            
            if findings:
                rows.append([Paragraph("Key findings: " + escape("; ".join(str(x) for x in findings)), styles["BodyText"])])
            if relevance:
                rows.append([Paragraph("Business relevance: " + escape(str(relevance)), styles["BodyText"])])
            
            rows.append([Paragraph(f'<link href={quoteattr(item.url)} color="#194B57">Source and citation</link>', styles["BodyText"])])
            
            table = Table(rows, colWidths=[170*mm]); table.setStyle(TableStyle([("BOX", (0,0), (-1,-1), .5, colors.HexColor("#CBD5D8")), ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#EEF5F5")), ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7), ("TOPPADDING", (0,0), (-1,-1), 7), ("BOTTOMPADDING", (0,0), (-1,-1), 7)]))
            story.append(KeepTogether([*([source_heading] if source_heading else []), table, Spacer(1, 4*mm)]))
    
    if items_without_summary > 0:
        story.insert(3, Paragraph(f"Note: {items_without_summary} items are showing raw content (AI summarization pending)", styles["BodyText"]))
        story.insert(4, Spacer(1, 4*mm))
    
    def footer(canvas, document):
        canvas.saveState(); canvas.setFont("Helvetica", 8); canvas.setFillColor(colors.grey); canvas.drawString(18*mm, 10*mm, "BridgeAI - reviewed intelligence"); canvas.drawRightString(A4[0]-18*mm, 10*mm, f"Page {document.page}"); canvas.restoreState()
    doc.multiBuild(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def build_comprehensive_pdf(session) -> bytes:
    """Export all persisted Daily Intelligence data across every batch."""
    buffer = BytesIO(); styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Brand", parent=styles["Title"], textColor=colors.HexColor("#194B57"), alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading1"], textColor=colors.HexColor("#194B57"), spaceBefore=12))
    styles.add(ParagraphStyle(name="Source", parent=styles["Heading2"], textColor=colors.HexColor("#C06B3E"), keepWithNext=True))
    styles.add(ParagraphStyle(name="ItemTitle", parent=styles["Heading3"], fontSize=10.5, leading=13, textColor=colors.HexColor("#173A43")))
    doc = NumberedDocTemplate(buffer, pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=17*mm, bottomMargin=17*mm,
                              title="BridgeAI Comprehensive Daily Intelligence")
    batches = session.query(IngestionBatch).order_by(IngestionBatch.created_at).all()
    legacy_reports = session.query(DailyIntelligenceReport).order_by(DailyIntelligenceReport.created_at).all()
    all_rows = session.query(DailyRawItem).filter(DailyRawItem.duplicate_of.is_(None)).order_by(DailyRawItem.source_type, DailyRawItem.source_name, DailyRawItem.published_at.desc()).all()
    # Global deduplication across historical batches while preserving batch provenance.
    canonical = {}; provenance = {}
    for row in all_rows:
        key = row.canonical_url or row.content_hash or row.id
        provenance.setdefault(key, []).append(row.batch_id)
        existing = canonical.get(key)
        if existing is None or len(row.cleaned_content or "") > len(existing.cleaned_content or ""):
            canonical[key] = row
    rows = list(canonical.values())
    summary_rows = session.query(DailySummary).filter(DailySummary.summary_level == "item").all()
    summaries = {}
    for summary in summary_rows:
        existing = summaries.get(summary.item_id)
        if existing is None or bool(summary.edited_summary_text): summaries[summary.item_id] = summary
    generated = datetime.now(UTC)
    story = [Paragraph("BridgeAI Comprehensive Daily Intelligence", styles["Brand"]), Spacer(1, 5*mm),
             Paragraph(f"Generated: {generated.strftime('%Y-%m-%d %H:%M UTC')}<br/>PostgreSQL batches included: {len(batches)}<br/>Legacy generated reports included: {len(legacy_reports)}<br/>Persisted canonical records: {len(all_rows)}<br/>Globally unique records in this report: {len(rows)}", styles["BodyText"]),
             Spacer(1, 5*mm), Paragraph("Batch Coverage", styles["Heading1"])]
    batch_data = [["Batch ID", "Created", "Status", "Fetched", "Unique"]]
    for batch in batches:
        batch_data.append([batch.id[:12], str(batch.created_at.date()), batch.status, str(batch.total_raw_items), str(batch.unique_items)])
    batch_table = Table(batch_data, colWidths=[40*mm, 28*mm, 35*mm, 22*mm, 22*mm], repeatRows=1)
    batch_table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#194B57")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#CBD5D8")), ("FONTSIZE", (0,0), (-1,-1), 8), ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5), ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5)]))
    if len(batch_data) == 1:
        story.append(Paragraph("No ingestion batches are currently stored.", styles["BodyText"]))
    else:
        story.append(batch_table)
    story.extend([Spacer(1, 6*mm), Paragraph("Table of Contents", styles["Heading1"]), TableOfContents(), PageBreak()])
    for source_type in SOURCE_TYPES:
        typed = [row for row in rows if row.source_type == source_type]
        story.append(Paragraph(f"{source_type.title()} ({len(typed)})", styles["Section"]))
        if not typed:
            story.append(Paragraph("No records are currently stored for this source category.", styles["BodyText"])); continue
        source_names = sorted({row.source_name for row in typed})
        for source_name in source_names:
            source_rows = [row for row in typed if row.source_name == source_name]
            story.append(Paragraph(f"{escape(source_name)} ({len(source_rows)})", styles["Source"]))
            for row in source_rows:
                summary = summaries.get(row.id)
                displayed = (summary.edited_summary_text or summary.summary_text) if summary else (row.cleaned_content or row.description or row.title)[:700]
                findings = summary.structured_summary_json.get("key_findings", []) if summary else []
                batch_ids = sorted(set(provenance.get(row.canonical_url or row.content_hash or row.id, [row.batch_id])))
                source_link = f'<link href={quoteattr(row.url)} color="#194B57">Open source / citation</link>'
                parts = [Paragraph(escape(row.title), styles["ItemTitle"]),
                         Paragraph(f"Published: {row.published_at.date() if row.published_at else 'Unknown'} | Review: {escape(row.review_status)} | Relevance: {row.relevance_score:.0f} | Credibility: {row.credibility_score:.0f}", styles["BodyText"]),
                         Paragraph(escape(displayed or "No summary content available."), styles["BodyText"])]
                if findings: parts.append(Paragraph("Key findings: " + escape("; ".join(str(x) for x in findings[:5])), styles["BodyText"]))
                parts.extend([Paragraph(f"Batch provenance: {escape(', '.join(x[:12] for x in batch_ids))}", styles["BodyText"]), Paragraph(source_link, styles["BodyText"]), Spacer(1, 3*mm)])
                story.append(KeepTogether(parts))
        story.append(PageBreak())
    if legacy_reports:
        story.append(Paragraph(f"Legacy Generated Reports ({len(legacy_reports)})", styles["Section"]))
        story.append(Paragraph("Reports created by the earlier Daily Intelligence workflow are retained below so the database export covers both platform workflows.", styles["BodyText"]))
        for legacy in legacy_reports:
            report = legacy.report or {}
            story.append(Paragraph(f"Report {escape(legacy.report_id[:16])} - {legacy.created_at.date()}", styles["Source"]))
            story.append(Paragraph(escape(str(report.get("executive_summary") or "No executive summary stored.")), styles["BodyText"]))
            for item in (report.get("top_developments") or []):
                if not isinstance(item, dict):
                    continue
                title = escape(str(item.get("title") or "Untitled development"))
                summary = escape(str(item.get("summary") or item.get("evidence_snippet") or ""))
                source = escape(str(item.get("source") or item.get("publisher") or "Unknown source"))
                url = str(item.get("url") or "")
                parts = [Paragraph(title, styles["ItemTitle"]), Paragraph(f"Source: {source}", styles["BodyText"])]
                if summary: parts.append(Paragraph(summary, styles["BodyText"]))
                if url: parts.append(Paragraph(f'<link href={quoteattr(url)} color="#194B57">Open source / citation</link>', styles["BodyText"]))
                parts.append(Spacer(1, 2*mm)); story.append(KeepTogether(parts))
        story.append(PageBreak())
    story.append(Paragraph("Source Integration Coverage", styles["Section"]))
    latest_runs = {}
    for run in session.query(DailySourceRun).order_by(DailySourceRun.completed_at.desc()).all():
        latest_runs.setdefault(run.source_name, run)
    coverage = [["Source", "Type", "Status", "Items", "Response"]]
    for name, run in sorted(latest_runs.items()):
        coverage.append([name, run.source_type, run.status, str(run.items_returned), f"{run.response_time_ms} ms"])
    if len(coverage) == 1:
        coverage.append(["No source runs stored", "-", "-", "0", "-"])
    coverage_table = Table(coverage, colWidths=[52*mm, 25*mm, 30*mm, 18*mm, 28*mm], repeatRows=1)
    coverage_table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#194B57")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#CBD5D8")), ("FONTSIZE", (0,0), (-1,-1), 7.5), ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4), ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
    story.append(coverage_table)
    def footer(canvas, document):
        canvas.saveState(); canvas.setFont("Helvetica", 8); canvas.setFillColor(colors.grey)
        canvas.drawString(16*mm, 9*mm, "BridgeAI - PostgreSQL intelligence archive")
        canvas.drawRightString(A4[0]-16*mm, 9*mm, f"Page {document.page}"); canvas.restoreState()
    doc.multiBuild(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
