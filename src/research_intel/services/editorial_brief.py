"""Stage 3: turn filtered signals into a source-grounded editorial brief."""
from __future__ import annotations

import asyncio
import json
import re
from io import BytesIO
from datetime import UTC, datetime
from typing import Any
from xml.sax.saxutils import escape

from research_intel.signal_filter.models import SignalItem


EDITORIAL_SYSTEM_PROMPT = """You are the Editorial Voice of Bridge AI Intelligence, a weekly
newsletter for enterprise Marketing, Sales, RevOps, and Analytics leaders. Translate source
material into benefit-led newsletter copy. Be confident, plain, skimmable, business-first, and
never hyped. Use only claims traceable to the supplied source. Never fabricate facts, numbers,
dates, names, quotes, or URLs. Preserve uncertainty. Skip items with no plausible near-term GTM
benefit. For each surviving item return headline, what_happened, why_it_matters, the_move,
function, and source. Headlines lead with reader payoff. The move is a concrete pilot, metric,
talk-track, or decision. Keep the exact source publication, date, and URL. Return valid JSON."""


def _pdf_text(value: Any) -> str:
    normalized = str(value or "").translate(str.maketrans({
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2011": "-", "\u2026": "...",
    }))
    return escape(normalized.encode("latin-1", "replace").decode("latin-1"))


def build_editorial_brief_pdf(brief: dict[str, Any]) -> bytes:
    """Render a generated editorial brief as a polished, source-linked PDF."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, leftMargin=0.62 * inch, rightMargin=0.62 * inch,
        topMargin=0.58 * inch, bottomMargin=0.62 * inch,
        title=str(brief.get("subject_line") or "Bridge AI Editorial Brief"),
        author="Bridge AI Intelligence",
    )
    base = getSampleStyleSheet()
    navy, blue, grey = colors.HexColor("#17324d"), colors.HexColor("#2f6f9f"), colors.HexColor("#5f6b76")
    title = ParagraphStyle("EditorialTitle", parent=base["Title"], fontSize=22, leading=27, textColor=navy, spaceAfter=8)
    subtitle = ParagraphStyle("EditorialSubtitle", parent=base["Heading2"], fontSize=13, leading=17, textColor=blue, spaceAfter=16)
    section = ParagraphStyle("EditorialSection", parent=base["Heading1"], fontSize=18, leading=22, textColor=navy, spaceAfter=12)
    item_head = ParagraphStyle("EditorialItemHead", parent=base["Heading2"], fontSize=13, leading=17, textColor=blue, spaceBefore=8, spaceAfter=6, keepWithNext=True)
    body = ParagraphStyle("EditorialBody", parent=base["BodyText"], fontSize=9.4, leading=13.5, textColor=colors.HexColor("#263746"), spaceAfter=6)
    meta = ParagraphStyle("EditorialMeta", parent=body, fontSize=8.4, leading=11, textColor=grey)
    overview = ParagraphStyle("EditorialOverview", parent=body, leftIndent=10, bulletIndent=0)
    story = [
        Paragraph("BRIDGE AI INTELLIGENCE", ParagraphStyle("Brand", parent=meta, textColor=blue, spaceAfter=5)),
        Paragraph("Editorial Ready Brief", title),
        Paragraph(_pdf_text(brief.get("subject_line")), subtitle),
        Paragraph(f"<b>This Week in Brief</b><br/>{_pdf_text(brief.get('this_week_in_brief'))}", body),
        Spacer(1, 8),
    ]
    for group in brief.get("sections", []):
        story.append(Paragraph(f"- {_pdf_text(group.get('section'))}: {int(group.get('count') or 0)} items", overview))

    for group in brief.get("sections", []):
        story.extend([PageBreak(), Paragraph(_pdf_text(group.get("section")), section)])
        for item in group.get("items", []):
            source = item.get("source") or {}
            publication = _pdf_text(source.get("publication") or "Publication unavailable")
            published = str(source.get("published_at") or "")[:10]
            url = str(source.get("url") or "")
            if url:
                source_line = f'<link href="{escape(url, {chr(34): "&quot;"})}" color="#2f6f9f">{publication}</link>'
            else:
                source_line = f"{publication} - link unavailable"
            if published:
                source_line += f" | {_pdf_text(published)}"
            story.extend([
                Paragraph(_pdf_text(item.get("headline")), item_head),
                Paragraph(f"<b>What happened:</b> {_pdf_text(item.get('what_happened'))}", body),
                Paragraph(f"<b>Why it matters:</b> {_pdf_text(item.get('why_it_matters'))}", body),
                Paragraph(f"<b>The move:</b> {_pdf_text(item.get('the_move'))}", body),
                Paragraph(f"<b>Function:</b> {_pdf_text(item.get('function'))}", meta),
                Paragraph(f"<b>Source:</b> {source_line}", meta),
                Spacer(1, 9),
            ])

    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#d9e2e9"))
        canvas.line(document.leftMargin, 0.45 * inch, letter[0] - document.rightMargin, 0.45 * inch)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(grey)
        canvas.drawString(document.leftMargin, 0.27 * inch, "Bridge AI Intelligence - Editorial Ready Brief")
        canvas.drawRightString(letter[0] - document.rightMargin, 0.27 * inch, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def _sentences(text: str, limit: int = 2) -> str:
    parts = re.split(r"(?<=[.!?])\s+", " ".join((text or "").split()))
    return " ".join(parts[:limit])[:650].strip()


def _function(item: SignalItem) -> str:
    text = f"{item.title} {item.body}".lower()
    matches = []
    if any(term in text for term in ("sales", "revenue", "crm", "pipeline", "lead", "account")):
        matches.append("Sales")
    if any(term in text for term in ("marketing", "campaign", "brand", "content", "demand", "growth")):
        matches.append("Marketing")
    if any(term in text for term in ("analytics", "insight", "data", "forecast", "metric", "intelligence")):
        matches.append("Analytics")
    return matches[0] if len(matches) == 1 else "Multiple" if matches else "Multiple"


def _source(item: SignalItem) -> dict[str, Any]:
    published = item.metadata.published_at
    return {
        "publication": item.metadata.source_name or "Publication unavailable",
        "published_at": published.isoformat() if published else None,
        "url": item.metadata.source_url,
        "link_available": bool(item.metadata.source_url),
    }


def _fallback_item(item: SignalItem) -> dict[str, Any]:
    function = _function(item)
    what = _sentences(item.body) or item.title
    payoff = {
        "Sales": "What sales leaders can take from",
        "Marketing": "What marketing leaders can use from",
        "Analytics": "What analytics leaders should test from",
        "Multiple": "The practical GTM takeaway from",
    }[function]
    implications = {
        "Sales": "This could affect sales productivity, pipeline quality, or revenue execution. Treat it as evidence for a focused workflow decision, not proof of a guaranteed outcome.",
        "Marketing": "This could affect campaign execution, customer engagement, or marketing efficiency. The source supports a small validation step before broader budget or headcount changes.",
        "Analytics": "This could improve how teams collect, explain, or act on business evidence. Validate the source claim against one existing metric before changing the wider analytics roadmap.",
        "Multiple": "This may affect more than one GTM function, but the immediate value is a clearer decision about where to test, fund, or wait. Keep the first experiment narrow enough to measure.",
    }
    moves = {
        "Sales": "Test the underlying idea in one pipeline stage and compare conversion rate, cycle time, and rep effort with the current process.",
        "Marketing": "Apply the idea to one campaign and compare turnaround time, engagement, and qualified pipeline with the existing workflow.",
        "Analytics": "Run a limited evaluation against one trusted dataset and compare accuracy, time-to-insight, and analyst review effort.",
        "Multiple": "Choose one cross-functional workflow, define one success metric, and run a small pilot before assigning wider budget or headcount.",
    }
    return {
        "item_id": item.item_id,
        "section": item.category,
        "headline": f"{payoff} {item.title}"[:180],
        "what_happened": what,
        "why_it_matters": implications[function],
        "the_move": moves[function],
        "function": function,
        "source": _source(item),
        "editorial_status": "ready",
    }


def _issue_synthesis(items: list[dict[str, Any]]) -> tuple[str, str]:
    if not items:
        return "No publishable signals cleared the editorial bar", "No source-grounded items were available for this issue."
    strongest = items[0]
    functions = list(dict.fromkeys(item["function"] for item in items[:8]))
    subject = strongest["headline"][:140]
    intro = (
        f"The clearest opportunity this week is {strongest['headline'].lower()}. "
        f"Across {', '.join(functions)}, the strongest signals point toward smaller, measurable workflow tests rather than broad transformation bets. "
        "The practical advantage comes from comparing each new approach with an existing operating metric before expanding spend. "
        "Use the briefs below to decide what deserves a pilot now, what needs validation, and what can wait."
    )
    return subject, intro


async def _enhance_with_openai(items: list[SignalItem], api_key: str, model: str = "gpt-4o-mini") -> dict[str, dict[str, Any]]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key)
    output: dict[str, dict[str, Any]] = {}

    async def process(chunk: list[SignalItem]) -> None:
        records = [{
            "item_id": item.item_id, "title": item.title, "raw_text": item.body[:1400],
            "section": item.category, "publication": item.metadata.source_name,
            "published_at": item.metadata.published_at.isoformat() if item.metadata.published_at else None,
            "url": item.metadata.source_url,
        } for item in chunk]
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": EDITORIAL_SYSTEM_PROMPT},
                {"role": "user", "content": "Rewrite these records. Return JSON as {items:[...]}.\n" + json.dumps(records)},
            ],
            response_format={"type": "json_object"}, temperature=0.2,
        )
        data = json.loads(response.choices[0].message.content or "{}")
        for value in data.get("items", []):
            item_id = value.get("item_id")
            if item_id:
                output[item_id] = value

    for start in range(0, len(items), 15):
        try:
            await process(items[start:start + 15])
        except Exception:
            continue
    return output


async def build_editorial_brief(run_id: str, items: list[SignalItem], api_key: str | None = None) -> dict[str, Any]:
    ordered = sorted(items, key=lambda item: (
        -(item.scores.business_relevance.score if item.scores else 0),
        -(item.scores.actionability.score if item.scores else 0),
        item.title.lower(),
    ))
    editorial_items = [_fallback_item(item) for item in ordered]
    ai_values = await _enhance_with_openai(ordered, api_key) if api_key else {}
    for index, (raw, fallback) in enumerate(zip(ordered, editorial_items, strict=True)):
        enhanced = ai_values.get(raw.item_id)
        if not enhanced or enhanced.get("skip"):
            continue
        # Source is always rebuilt from the record so the model cannot alter it.
        editorial_items[index] = {
            **fallback,
            **{key: enhanced[key] for key in ("headline", "what_happened", "why_it_matters", "the_move", "function") if enhanced.get(key)},
            "source": _source(raw),
        }
    subject, intro = _issue_synthesis(editorial_items)
    sections = [{
        "section": section,
        "count": len(section_items),
        "items": section_items,
    } for section in dict.fromkeys(item["section"] for item in editorial_items)
      if (section_items := [item for item in editorial_items if item["section"] == section])]
    return {
        "run_id": run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "subject_line": subject,
        "this_week_in_brief": intro,
        "item_count": len(editorial_items),
        "sections": sections,
        "items": editorial_items,
        "generation_mode": "openai_with_fallback" if api_key else "deterministic_source_grounded",
    }
