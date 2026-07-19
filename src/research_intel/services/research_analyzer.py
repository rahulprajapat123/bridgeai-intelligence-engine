"""Comprehensive Research Paper Analyzer with AI"""
from __future__ import annotations

import json
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

from research_intel.config import Settings
from research_intel.ingestion.base import RawDocument


class ResearchAnalysis(BaseModel):
    """Comprehensive AI analysis of a research paper"""
    summary: str = Field(description="2-3 sentence executive summary")
    key_findings: list[str] = Field(description="3-5 main findings or contributions")
    business_impact: str = Field(description="Practical business applications and impact")
    technologies: list[str] = Field(description="Technologies, methods, or algorithms mentioned")
    keywords: list[str] = Field(description="Key topics and themes")
    industry: list[str] = Field(description="Relevant industries (e.g., healthcare, finance, retail)")
    atomic_insights: list[str] = Field(description="Actionable insights (5-10 bullet points)")
    research_type: str = Field(description="Type: theoretical, empirical, survey, case_study, etc.")
    target_audience: list[str] = Field(description="Who should care: researchers, engineers, executives, etc.")
    limitations: str = Field(description="Key limitations or constraints mentioned")
    future_work: str = Field(description="Suggested future research directions")


class ResearchPaperAnalyzer:
    """
    Comprehensive AI-powered research paper analysis.
    
    Extracts:
    - Summary
    - Key Findings
    - Business Impact
    - Technologies
    - Keywords
    - Industry
    - Atomic Insights
    """
    
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: OpenAI | None = None
        if settings.openai_api_key:
            self._client = OpenAI(api_key=settings.openai_api_key)
    
    def analyze(self, document: RawDocument) -> dict[str, Any] | None:
        """
        Analyze a research paper and extract comprehensive insights.
        
        Returns structured analysis or None if analysis fails.
        """
        if not self._client:
            return None
        
        # Only analyze academic papers with sufficient content
        if document.source_type != "academic":
            return None
        
        text_length = len(document.text or "")
        if text_length < 500:
            return None
        
        try:
            return self._analyze_with_llm(document)
        except Exception as e:
            print(f"Analysis failed for {document.title[:50]}: {e}")
            return None
    
    def _analyze_with_llm(self, document: RawDocument) -> dict[str, Any]:
        """Use GPT-4 to perform comprehensive analysis"""
        
        # Truncate very long papers to fit context window
        text = document.text[:15000]
        
        prompt = f"""You are analyzing a research paper for a business intelligence platform.
Extract comprehensive insights that will be valuable for executives, researchers, and engineers.

**Research Paper:**
Title: {document.title}
Authors: {', '.join(document.authors[:5]) if document.authors else 'Unknown'}
Source: {document.source_name}
URL: {document.source_url}

**Full Text:**
{text}

**Instructions:**
Analyze this paper and return a JSON object with the following fields:

1. **summary**: 2-3 sentence executive summary (what is this paper about?)
2. **key_findings**: Array of 3-5 main findings or contributions
3. **business_impact**: Description of practical business applications and real-world impact
4. **technologies**: Array of specific technologies, methods, algorithms, or frameworks mentioned
5. **keywords**: Array of 5-10 key topics, themes, or concepts
6. **industry**: Array of relevant industries (e.g., "healthcare", "finance", "retail", "manufacturing")
7. **atomic_insights**: Array of 5-10 actionable bullet-point insights
8. **research_type**: One of: "theoretical", "empirical", "survey", "case_study", "experimental", "review"
9. **target_audience**: Array (e.g., ["researchers", "ML engineers", "CTOs", "data scientists"])
10. **limitations**: Brief description of key limitations or constraints mentioned in the paper
11. **future_work**: Brief description of future research directions suggested

**Return ONLY valid JSON. No markdown, no explanations.**
"""
        
        assert self._client is not None
        
        response = self._client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        
        content = response.choices[0].message.content or "{}"
        analysis = json.loads(content)
        
        # Validate structure
        required_fields = [
            "summary", "key_findings", "business_impact", "technologies",
            "keywords", "industry", "atomic_insights"
        ]
        
        for field in required_fields:
            if field not in analysis:
                raise ValueError(f"Missing required field: {field}")
        
        return analysis
    
    def enrich_metadata(self, metadata: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
        """
        Merge analysis results into document metadata.
        
        This creates a rich metadata structure for the knowledge base.
        """
        enriched = metadata.copy()
        
        enriched.update({
            "ai_summary": analysis.get("summary", ""),
            "key_findings": analysis.get("key_findings", []),
            "business_impact": analysis.get("business_impact", ""),
            "technologies": analysis.get("technologies", []),
            "keywords": analysis.get("keywords", []),
            "industries": analysis.get("industry", []),
            "atomic_insights": analysis.get("atomic_insights", []),
            "research_type": analysis.get("research_type", ""),
            "target_audience": analysis.get("target_audience", []),
            "limitations": analysis.get("limitations", ""),
            "future_work": analysis.get("future_work", ""),
            "analyzed": True,
        })
        
        return enriched
