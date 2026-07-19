# Signal Filter scoring rubric

Eligible items receive integer 0–5 scores for business relevance, actionability, novelty, credibility, and momentum. Each criterion carries confidence, rationale, and evidence. Every individual minimum must pass and the total must reach 15.

Production providers should use source-specific credibility evidence: named reporting and primary links for news; ownership, methodology, and promotional bias for blogs; maintenance, tests, license, contributors, releases, and security for repositories; and venue, method, sample, baselines, reproducibility, limitations, and correction status for papers. Stars or a single static engagement count are never sufficient momentum evidence.

Recency is a separate exponential weight with source-type half-lives. If trend history is absent, momentum confidence must be low. The bundled heuristic fallback is for offline development and is not equivalent to production AI scoring.
