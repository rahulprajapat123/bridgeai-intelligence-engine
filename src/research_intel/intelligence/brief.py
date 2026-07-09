from __future__ import annotations

import re
from collections import Counter

from research_intel.intelligence.domain import DomainClassifier, STOPWORDS
from research_intel.schemas import BriefAnalysis, ProjectContextInput, SourceRoute
from research_intel.utils import sentence_split, tokenize, unique_keep_order


DELIVERABLE_TERMS = {
    "executive report": "Executive Report",
    "detailed report": "Detailed Report",
    "ppt": "PowerPoint Deck",
    "powerpoint": "PowerPoint Deck",
    "dashboard": "Dashboard",
    "comparison": "Competitor Comparison",
    "audience matrix": "Audience Matrix",
    "partner feedback": "Partner Feedback and Sentiment",
    "sentiment": "Partner Feedback and Sentiment",
    "search analytics": "Search Analytics Analysis",
    "social listening": "Social Listening Analysis",
    "competitive ad analysis": "Competitive Ad Analysis",
    "intel vs competitor": "Intel vs Competitor Comparison",
    "benchmark": "Benchmark",
    "static rag dashboard": "Static RAG Dashboard",
}


class BriefUnderstandingService:
    def __init__(self, classifier: DomainClassifier | None = None) -> None:
        self.classifier = classifier or DomainClassifier()

    def analyze(self, text: str) -> BriefAnalysis:
        domain = self.classifier.classify(text)
        routes = self.classifier.routes_for(domain.domain)
        expansions = self.classifier.expansions_for(domain.domain)
        keywords = self._keywords(text)
        deliverables = self._deliverables(text)
        constraints = self._constraints(text)
        dependencies = self._section_or_sentence_matches(
            text, ("depend", "requires", "required", "access", "export", "input")
        )
        risks = self._section_or_sentence_matches(
            text, ("risk", "blocked", "limitation", "out of scope", "cannot", "assumption")
        )
        inputs = self._section_or_sentence_matches(text, ("input", "source", "export", "upload"))
        outputs = deliverables + self._section_or_sentence_matches(text, ("output", "deliverable"))
        timeline = self._section_or_sentence_matches(text, ("timeline", "week", "day", "deadline"))
        competitors = self._competitors(text)
        entities = self._entities(text)
        intent = self._intent(domain.domain, text)
        objective = self._objective(text, intent)
        subqueries = self._query_decomposition(text, domain.domain, competitors, expansions)
        route_plan = self._source_route_plan(domain.primary_domain or domain.domain, subqueries, routes)

        return BriefAnalysis(
            title=self._title(text, intent),
            domain=domain,
            primary_domain=domain.primary_domain or domain.domain,
            secondary_domains=domain.secondary_domains,
            objective=objective,
            intent=intent,
            audience=self._audience(text),
            companies=competitors,
            entities=entities,
            competitors=competitors,
            technologies=self._technologies(text),
            tools_or_platforms=self._tools_or_platforms(text),
            keywords=keywords,
            query_decomposition=subqueries,
            research_questions=subqueries,
            retrieval_routes=routes,
            source_routes=routes,
            source_route_plan=route_plan,
            structured_constraints=constraints,
            constraints=constraints,
            deliverables=unique_keep_order(deliverables),
            dependencies=unique_keep_order(dependencies)[:12],
            risks=unique_keep_order(risks)[:12],
            out_of_scope=self._out_of_scope(text),
            inputs=unique_keep_order(inputs)[:12],
            outputs=unique_keep_order(outputs)[:12],
            timeline=unique_keep_order(timeline)[:8],
            confidence=domain.confidence,
            inferred_project_context=self._infer_project_context(text, domain.domain, constraints),
        )

    def _title(self, text: str, intent: str) -> str:
        for sentence in sentence_split(text):
            cleaned = sentence.strip()
            if 8 <= len(cleaned) <= 120:
                return cleaned
        return intent

    def _objective(self, text: str, intent: str) -> str:
        for sentence in sentence_split(text):
            if re.search(r"\b(objective|goal|purpose|need|analyze|assess|recommend|compare)\b", sentence, re.I):
                return sentence[:260]
        return intent

    def _keywords(self, text: str) -> list[str]:
        tokens = [
            token
            for token in tokenize(text)
            if token not in STOPWORDS and len(token) > 2 and not token.isdigit()
        ]
        counts = Counter(tokens)
        phrases = []
        lowered = text.lower()
        for phrase in (
            "partner program",
            "competitive benchmarking",
            "audience matrix",
            "social listening",
            "search analytics",
            "deal registration",
            "market development funds",
            "retrieval augmented generation",
            "hybrid search",
            "vector search",
            "legal contract analysis",
        ):
            if phrase in lowered:
                phrases.append(phrase)
        return unique_keep_order(phrases + [token for token, _ in counts.most_common(18)])[:20]

    def _deliverables(self, text: str) -> list[str]:
        lowered = text.lower()
        found = [label for term, label in DELIVERABLE_TERMS.items() if term in lowered]
        for sentence in sentence_split(text):
            if re.search(r"\b(deliverable|output|produce|create|build)\b", sentence, re.I):
                found.append(sentence[:180])
        return found

    def _constraints(self, text: str) -> dict[str, bool | str | list[str]]:
        lowered = text.lower()
        constraints: dict[str, bool | str | list[str]] = {
            "portal_access_required": bool(re.search(r"portal access|login|authenticated", lowered)),
            "primary_research_out_of_scope": "primary research" in lowered
            and bool(re.search(r"out of scope|not required|exclude", lowered)),
            "requires_client_data": bool(re.search(r"client data|first-party|internal export", lowered)),
            "requires_third_party_exports": bool(
                re.search(r"brightedge|sprinklr|adbeat|third-party export", lowered)
            ),
            "requires_brightedge_export": "brightedge" in lowered,
            "requires_sprinklr_export": "sprinklr" in lowered,
            "requires_adbeat_export": "adbeat" in lowered,
            "depends_on_intel_data": "intel" in lowered,
            "time_limitations": "",
            "budget_limitations": "",
        }
        explicit = self._section_or_sentence_matches(
            text, ("constraint", "must", "required", "out of scope", "cannot", "depends")
        )
        if explicit:
            constraints["explicit_constraints"] = explicit[:10]
        return constraints

    def _audience(self, text: str) -> list[str]:
        lowered = text.lower()
        audience: list[str] = []
        for label, terms in {
            "executives": ("executive", "leadership", "c-suite"),
            "marketing team": ("marketing", "co-marketing", "mdf"),
            "partner team": ("partner", "channel"),
            "developers": ("developer", "engineering", "sdk", "api"),
            "legal team": ("legal", "compliance", "contract"),
        }.items():
            if any(term in lowered for term in terms):
                audience.append(label)
        return audience

    def _technologies(self, text: str) -> list[str]:
        candidates = [
            "RAG",
            "LLM",
            "Vector Search",
            "Hybrid Search",
            "BM25",
            "Cross-Encoder",
            "OpenAI",
            "Claude",
            "Gemini",
        ]
        lowered = text.lower()
        return [candidate for candidate in candidates if candidate.lower() in lowered]

    def _tools_or_platforms(self, text: str) -> list[str]:
        candidates = [
            "BrightEdge",
            "Sprinklr",
            "Adbeat",
            "G2",
            "Gartner Peer Insights",
            "GitHub",
            "Semantic Scholar",
            "OpenAlex",
            "Serper",
            "Exa",
        ]
        lowered = text.lower()
        return [candidate for candidate in candidates if candidate.lower() in lowered]

    def _out_of_scope(self, text: str) -> list[str]:
        matches = []
        for sentence in sentence_split(text):
            if re.search(r"\b(out of scope|not required|exclude|do not|cannot)\b", sentence, re.I):
                matches.append(sentence[:220])
        return matches

    def _source_route_plan(
        self, primary_domain: str, queries: list[str], routes: list[str]
    ) -> list[SourceRoute]:
        source_type_labels = {
            "serper": "open_web_search",
            "exa": "neural_web_search",
            "tavily": "web_research",
            "newsapi": "industry_news",
            "gnews": "industry_news",
            "github": "repositories",
            "semantic_scholar": "academic_papers",
            "openalex": "academic_papers",
            "arxiv": "preprints",
            "technical_blogs": "technical_blogs",
            "firecrawl": "full_page_parse",
            "apify": "authenticated_or_deep_scrape",
        }
        default_query = queries[0] if queries else primary_domain.replace("_", " ").lower()
        return [
            SourceRoute(
                source_type=source_type_labels.get(route, route),
                priority=index + 1,
                query=queries[index] if index < len(queries) else default_query,
            )
            for index, route in enumerate(routes[:8])
        ]

    def _section_or_sentence_matches(self, text: str, terms: tuple[str, ...]) -> list[str]:
        matches: list[str] = []
        for sentence in sentence_split(text):
            lowered = sentence.lower()
            if any(term in lowered for term in terms):
                matches.append(sentence[:220])
        return matches

    def _competitors(self, text: str) -> list[str]:
        candidates = [
            "Intel",
            "Microsoft",
            "Nvidia",
            "AMD",
            "AWS",
            "Google",
            "Oracle",
            "IBM",
            "OpenAI",
            "Anthropic",
            "Meta",
        ]
        lowered = text.lower()
        return [candidate for candidate in candidates if candidate.lower() in lowered]

    def _entities(self, text: str) -> list[str]:
        matches = re.findall(r"\b[A-Z][A-Za-z0-9&.-]*(?:\s+[A-Z][A-Za-z0-9&.-]*){0,3}", text)
        cleaned = [
            match.strip()
            for match in matches
            if len(match.strip()) > 2 and match.lower() not in {"the", "this"}
        ]
        return unique_keep_order(cleaned)[:25]

    def _intent(self, domain_label: str, text: str) -> str:
        lowered = text.lower()
        if "partner" in lowered and ("benchmark" in lowered or "competitive" in lowered):
            return "Partner ecosystem competitive benchmarking"
        if "rag" in lowered or "retrieval augmented generation" in lowered:
            return "Evidence-backed RAG architecture recommendation"
        if "sentiment" in lowered:
            return "Sentiment and market signal analysis"
        return f"{domain_label} evidence synthesis"

    def _query_decomposition(
        self, text: str, domain_label: str, competitors: list[str], expansions: list[str]
    ) -> list[str]:
        queries = list(expansions)
        lowered = text.lower()
        if "partner" in lowered:
            competitor_terms = " ".join(competitors[:5]) if competitors else ""
            queries.extend(
                [
                    f"{competitor_terms} partner program comparison MDF enablement".strip(),
                    "CRN Channel Futures Channelnomics partner program benchmark",
                    "partner portal deal registration co-marketing enablement best practices",
                ]
            )
        if "brightedge" in lowered or "search analytics" in lowered:
            queries.append("BrightEdge competitive search analytics methodology")
        if "sprinklr" in lowered or "social listening" in lowered:
            queries.append("Sprinklr social listening competitive sentiment methodology")
        if "rag" in lowered or "retrieval" in lowered:
            queries.append("RAG retrieval reranking evaluation benchmark failure modes")
        return unique_keep_order([query for query in queries if query])[:10]

    def _infer_project_context(
        self, text: str, domain_label: str, constraints: dict[str, bool | str | list[str]]
    ) -> ProjectContextInput:
        lowered = text.lower()
        problem_type = "QA" if ("question" in lowered or "recommend" in lowered) else "search"
        if "summar" in lowered:
            problem_type = "summarization"
        if "classification" in lowered:
            problem_type = "classification"

        data_modality = "mixed"
        if "pdf" in lowered:
            data_modality = "PDFs"
        elif "code" in lowered or "repository" in lowered:
            data_modality = "code"
        elif "log" in lowered:
            data_modality = "logs"
        elif "structured" in lowered:
            data_modality = "structured"

        scale_match = re.search(r"\b(\d+[KkMm]?|\d{1,3}(?:,\d{3})+)\s+(documents|docs|records)", text)
        scale = scale_match.group(0) if scale_match else None
        latency_match = re.search(r"(<\s*\d+s|\d+\s*-\s*\d+s|>\s*\d+s)", text)
        latency = latency_match.group(0).replace(" ", "") if latency_match else None
        tradeoff = "accuracy_first" if re.search(r"high precision|accuracy|evidence-backed", lowered) else None
        if "budget" in lowered or "cost" in lowered:
            tradeoff = "balanced" if tradeoff else "cost_first"
        env = None
        for candidate in ("GCP", "AWS", "Azure", "on-prem", "hybrid", "edge"):
            if candidate.lower() in lowered:
                env = candidate
                break

        return ProjectContextInput(
            problem_type=problem_type,
            data_modality=data_modality,
            corpus_scale=scale,
            latency_constraint=latency,
            accuracy_cost_tradeoff=tradeoff,
            deployment_env=env,
            domain=domain_label,
            extra_constraints=constraints,
        )
