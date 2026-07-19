from __future__ import annotations

from research_intel.schemas import BriefAnalysis
from research_intel.services.evidence_ranker import RankedEvidence
from research_intel.utils import unique_keep_order


class ImplementationPlanner:
    def build(
        self,
        brief_text: str,
        analysis: BriefAnalysis,
        evidence: list[RankedEvidence],
        warnings: list[str],
    ) -> dict:
        domain = analysis.primary_domain or analysis.domain.domain
        tools = self._tools(analysis, evidence)
        apis = self._apis(evidence)
        steps = self._steps(analysis, bool(evidence))
        architecture = self._architecture(domain, tools, bool(evidence))
        risks = self._risks(analysis, warnings, bool(evidence))
        return {
            "recommended_approach": self._approach(domain, bool(evidence)),
            "why_this_approach": self._reasoning(evidence),
            "architecture": architecture,
            "tools_and_technologies": tools,
            "apis_required": apis,
            "implementation_steps": steps,
            "timeline": self._timeline(analysis),
            "cost_estimate": self._cost_estimate(apis),
            "risks_and_mitigations": risks,
            "alternatives": self._alternatives(domain),
        }

    def _approach(self, domain: str, has_evidence: bool) -> str:
        if any(term in domain.lower() for term in ("sales", "revenue")):
            return (
                "Build a governed revenue-intelligence decision layer on top of the existing CRM and warehouse. "
                "Unify opportunity, conversation, marketing, product-usage, and customer-success signals; generate "
                "pipeline-risk, churn-risk, and next-best-action recommendations; attach evidence citations to every "
                "recommendation; and require human approval before updates reach seller workflows. Validate it in a "
                "90-day pilot before deciding whether to expand the internal build or adopt a commercial platform."
            )
        if has_evidence:
            return (
                f"Use a domain-aware research workflow for {domain}: classify the brief, retrieve source-backed "
                "evidence, rank by credibility and implementation usefulness, then convert the evidence into a "
                "manager-presentable implementation plan."
            )
        return (
            f"Start with a brief-driven implementation plan for {domain}, then rerun evidence collection after "
            "source credentials or network access are available."
        )

    def _reasoning(self, evidence: list[RankedEvidence]) -> str:
        if not evidence:
            return "No external sources were available, so the plan is based on the uploaded brief and should be validated before final decisions."
        top_sources = ", ".join(item.document.source_name for item in evidence[:4])
        return f"The recommendation is grounded in the highest-ranked available evidence from {top_sources}, weighted for relevance, authority, freshness, and practical implementation value."

    def _architecture(self, domain: str, tools: list[str], has_evidence: bool) -> str:
        if any(term in domain.lower() for term in ("sales", "revenue")):
            return (
                "1. Source connectors: Salesforce/HubSpot CRM, call transcripts, marketing engagement, product telemetry, "
                "and customer-success records. 2. Governed data layer in Snowflake with identity resolution, consent, "
                "retention, and row-level access policies. 3. Feature and evidence layer for account timelines, pipeline "
                "signals, and citation-ready source records. 4. Modeling layer for forecast risk, churn risk, and ranked "
                "next-best actions with calibrated confidence. 5. Policy layer enforcing RBAC, PII redaction, audit logs, "
                "human approval, and abstention on weak evidence. 6. Activation through Salesforce, HubSpot, and Slack, "
                "with an evaluation dashboard tracking lift, false alerts, adoption, and time saved."
            )
        evidence_layer = "External evidence retrieval and ranking layer" if has_evidence else "Brief-only analysis layer until sources are configured"
        return (
            f"1. Brief intake and document parsing. 2. Domain classification for {domain}. "
            f"3. Query planning and source routing. 4. {evidence_layer}. "
            "5. Recommendation synthesis with source table and risk review. "
            f"6. Delivery layer using {', '.join(tools[:4]) or 'the existing FastAPI and browser UI'}."
        )

    def _tools(self, analysis: BriefAnalysis, evidence: list[RankedEvidence]) -> list[str]:
        tools = [
            "FastAPI",
            "SQLite locally / PostgreSQL in production",
            "Domain-aware source routing",
            "Weighted evidence ranking",
        ]
        tools.extend(analysis.tools_or_platforms)
        tools.extend(analysis.technologies)
        if any(term in (analysis.primary_domain or "").lower() for term in ("sales", "revenue")):
            tools.extend([
                "Salesforce or HubSpot APIs", "Snowflake", "dbt", "Airbyte or Fivetran",
                "FastAPI", "MLflow", "Great Expectations", "OpenTelemetry",
                "OPA or application RBAC", "Slack API",
            ])
        for item in evidence[:8]:
            if item.document.source_name not in tools:
                tools.append(item.document.source_name)
        return unique_keep_order(tools)[:14]

    def _apis(self, evidence: list[RankedEvidence]) -> list[str]:
        names = []
        for item in evidence:
            name = item.document.source_name
            if name not in names:
                names.append(name)
        return names[:12]

    def _steps(self, analysis: BriefAnalysis, has_evidence: bool) -> list[str]:
        if any(term in (analysis.primary_domain or "").lower() for term in ("sales", "revenue")):
            return [
                "Weeks 1-2: Baseline pipeline accuracy, churn recall, rep research time, action acceptance, and data quality; define the 90-day pilot cohort and control group.",
                "Weeks 2-4: Connect CRM, calls, marketing, product, and customer-success data; establish account identity, lineage, permissions, retention, and PII rules.",
                "Weeks 4-6: Create source-grounded account timelines and features; train or configure pipeline-risk and churn models; calibrate confidence and abstention thresholds.",
                "Weeks 6-8: Generate cited next-best actions, add manager approval, and integrate approved outputs into Salesforce/HubSpot and Slack.",
                "Weeks 8-10: Run offline back-tests and red-team citation, leakage, bias, security, and false-alert failure modes.",
                "Weeks 10-13: Run the controlled pilot; compare forecast error, churn detection, conversion, cycle time, user adoption, and hours saved against baseline.",
                "At day 90: Decide build, buy, or hybrid using measured lift, operating cost, integration fit, governance coverage, and switching risk.",
            ]
        steps = [
            "Confirm objective, audience, deliverables, constraints, and success criteria with the business owner.",
            "Finalize domain-specific search queries and source inclusion rules.",
        ]
        if has_evidence:
            steps.extend(
                [
                    "Review the ranked source table and mark any weak, duplicate, or vendor-only sources.",
                    "Translate evidence-backed findings into architecture, tool choices, and operating assumptions.",
                ]
            )
        else:
            steps.append("Configure at least one external source API or use free sources, then rerun evidence collection.")
        steps.extend(
            [
                "Build the minimum viable workflow and validate outputs with representative briefs.",
                "Add monitoring for failed sources, stale evidence, and low-confidence recommendations.",
                "Package the final implementation plan, risks, cost assumptions, and alternatives for stakeholder review.",
            ]
        )
        if analysis.deliverables:
            steps.insert(1, f"Prioritize requested deliverables: {', '.join(analysis.deliverables[:4])}.")
        return steps

    def _timeline(self, analysis: BriefAnalysis) -> list[str]:
        if analysis.timeline and not any(term in " ".join(analysis.timeline).lower() for term in ("pilot", "90-day", "90 day")):
            return analysis.timeline[:6]
        if any(term in (analysis.primary_domain or "").lower() for term in ("sales", "revenue")):
            return ["Days 1-30: data, governance, baseline, and prototype", "Days 31-60: models, cited recommendations, approvals, and integrations", "Days 61-90: controlled pilot, evaluation, and build-vs-buy decision"]
        return [
            "Day 1-2: Confirm scope, success criteria, and source access.",
            "Day 3-5: Implement intake, routing, retrieval, ranking, and error handling.",
            "Week 2: Validate evidence quality, tune scoring, and prepare stakeholder-ready outputs.",
            "Week 3: Production hardening, monitoring, documentation, and rollout.",
        ]

    def _cost_estimate(self, apis: list[str]) -> str:
        if not apis:
            return "Low initial cost. Uses local analysis only until external source APIs are configured."
        paid = [name for name in apis if name in {"Exa", "Tavily", "Serper", "Firecrawl", "Apify Web Scraper"}]
        if paid:
            return f"Moderate variable cost depending on usage of paid search/scraping APIs: {', '.join(paid)}. Prefer free/public sources first."
        return "Low to moderate. Current evidence set can use free/public or already configured APIs."

    def _risks(self, analysis: BriefAnalysis, warnings: list[str], has_evidence: bool) -> list[dict[str, str]]:
        risks = [
            {
                "risk": "Source coverage gaps",
                "mitigation": "Expose warnings, use free sources first, and rerun when missing API keys are configured.",
            },
            {
                "risk": "Stale or low-authority evidence",
                "mitigation": "Weight freshness and authority in ranking; require stakeholder review for critical claims.",
            },
        ]
        if not has_evidence:
            risks.append(
                {
                    "risk": "No external sources found",
                    "mitigation": "Treat the plan as preliminary and validate with external sources before committing budget.",
                }
            )
        for item in analysis.risks[:5]:
            risks.append({"risk": item, "mitigation": "Validate this assumption during discovery and track it in the delivery plan."})
        return risks

    def _alternatives(self, domain: str) -> list[str]:
        return [
            f"Brief-only advisory plan for {domain} when external research is not required.",
            "Manual analyst review using the same query plan and source table.",
            "Deeper paid/private-source enrichment if Gartner, Forrester, or specialist data exports are later configured.",
        ]
