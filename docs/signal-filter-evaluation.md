# Signal Filter evaluation

Tests cover stable defaults, normalization, URL canonicalization, similarity, decay, exact and lexical duplicates, non-compensable minimums, confidence review, category caps, deny-list QA, and audit reason codes. No test makes a paid API call.

Production evaluation still needs a labeled corpus containing exact/semantic duplicates, same-event and related non-duplicate pairs, source-quality contrasts, unsupported claims, and generic generated language. Report duplicate/event precision and recall, reviewer score agreement, false positives and negatives, regeneration success, source diversity, and cost per accepted item. Threshold changes should be compared on a held-out set before rollout.
