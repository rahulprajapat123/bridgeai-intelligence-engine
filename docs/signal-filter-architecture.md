# Signal Filter architecture

The signal filter is an additive, typed pipeline under `research_intel.signal_filter`. Raw title and body fields are preserved while normalized fields and stable fingerprints are derived. Cheap validation and exact/lexical duplicate checks run before optional embedding or intelligence-provider calls. A failure is terminal unless its decision explicitly routes the item to review.

```mermaid
flowchart TD
 A[Source ingestion] --> B[Normalization]
 B --> C[Metadata validation]
 C --> D[Exact deduplication]
 D --> E[Lexical deduplication]
 E --> F[Optional semantic deduplication]
 F --> G[Classification and claim extraction]
 G --> H[Event clustering]
 H --> I[Recency and five-criterion scoring]
 I --> J[Confidence decision]
 J --> K[Diversity and volume caps]
 K --> L[Language QA and targeted regeneration]
 L --> M[Accepted, review, rejected, duplicate, or volume-cut output]
 M --> N[Audit decisions and metrics]
```

`EmbeddingProvider`, `IntelligenceProvider`, and `HistoricalRepository` are protocols. Production deployments can inject OpenAI, local, or other implementations without coupling pipeline stages to one vendor. In the absence of an intelligence provider, heuristic scores are marked by low confidence and normally enter human review.

Event clustering currently uses conservative title similarity. Semantic event extraction, primary-source selection, unique-claim merging, and independent-confirmation retention require a configured intelligence provider and production corpus.
