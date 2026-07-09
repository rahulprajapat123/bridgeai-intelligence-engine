from __future__ import annotations

from datetime import UTC, datetime


class NewsletterBuilder:
    def build(self, *, topics: list[str], ranked_items: list[dict], max_items: int) -> dict:
        top = ranked_items[: min(max_items, 8)]
        marketing = self._filter(ranked_items, ("marketing", "martech", "campaign", "customer"))
        sales = self._filter(ranked_items, ("sales", "revenue", "crm", "enablement"))
        insights = self._filter(ranked_items, ("insight", "analytics", "business intelligence", "dashboard", "market intelligence"))
        agentic = self._filter(ranked_items, ("agentic", "llm", "rag", "openai", "claude", "gemini", "automation"))
        papers = [item for item in ranked_items if item["source_type"] == "academic"][:max_items]
        repos = [item for item in ranked_items if item["source_type"] == "code"][:max_items]

        newsletter_angles = self._angles(top, topics)
        return {
            "executive_summary": self._summary(top, topics),
            "top_developments": top,
            "marketing_ai": marketing[:max_items],
            "sales_ai": sales[:max_items],
            "insights_analytics": insights[:max_items],
            "agentic_ai_llm_rag": agentic[:max_items],
            "important_papers": papers,
            "github_repositories": repos,
            "newsletter_angles": newsletter_angles,
            "newsletter_draft": self._draft(top, newsletter_angles),
            "source_table": [self._source_row(item) for item in ranked_items[:max_items]],
        }

    def _summary(self, items: list[dict], topics: list[str]) -> str:
        if not items:
            return (
                "No current source-backed developments were found for the selected topics. "
                "Configure at least one news, search, paper, or GitHub source and rerun the report."
            )
        topic_text = ", ".join(topics[:6]) if topics else "AI for marketing, sales, insights, analytics, automation, LLMs, and RAG"
        publishers = ", ".join(dict.fromkeys(item["source"] for item in items[:5]))
        return (
            f"This intelligence brief covers {len(items)} high-priority developments across {topic_text}. "
            f"The strongest signals came from {publishers}. Items were ranked for recency, source authority, "
            "business relevance, and newsletter usefulness."
        )

    def _draft(self, items: list[dict], angles: list[dict]) -> str:
        if not items:
            return "No newsletter draft was generated because no source-backed developments were found."
        lines = [
            "AI Developments to Watch Across Marketing, Sales and Insights",
            "",
            "This month’s signal: AI adoption is moving from broad experimentation toward practical workflows, automation, analytics, and better evidence-backed decision support.",
            "",
            "Key developments:",
        ]
        for index, item in enumerate(items[:8], start=1):
            lines.extend(
                [
                    f"{index}. {item['title']}",
                    f"What happened: {item['summary']}",
                    f"Why it matters: {item['why_it_matters']}",
                    f"Business relevance: {item['business_relevance']}",
                    f"Source: {item['source']} - {item['url']}",
                    "",
                ]
            )
        lines.append("What businesses should watch next:")
        for angle in angles[:5]:
            lines.append(f"- {angle['title']}: {angle['summary']}")
        return "\n".join(lines).strip()

    def _angles(self, items: list[dict], topics: list[str]) -> list[dict]:
        if not items:
            return []
        output = []
        for item in items[:6]:
            output.append(
                {
                    "title": f"What {item['category']} leaders should watch",
                    "summary": item["business_relevance"],
                    "source": item["source"],
                    "url": item["url"],
                }
            )
        if topics:
            output.append(
                {
                    "title": "Cross-functional newsletter theme",
                    "summary": f"Connect {', '.join(topics[:4])} into one narrative about practical AI adoption and measurable business value.",
                    "source": "Report synthesis",
                    "url": "",
                }
            )
        return output

    def _filter(self, items: list[dict], terms: tuple[str, ...]) -> list[dict]:
        output = []
        for item in items:
            text = " ".join([item["title"], item["summary"], item["category"]]).lower()
            if any(term in text for term in terms):
                output.append(item)
        return output

    def _source_row(self, item: dict) -> dict:
        return {
            "title": item["title"],
            "url": item["url"],
            "source_type": item["source_type"],
            "publisher": item["source"],
            "date": item["date"],
            "confidence_score": item["confidence_score"],
            "evidence_snippet": item["summary"],
            "why_relevant": item["why_it_matters"],
        }
