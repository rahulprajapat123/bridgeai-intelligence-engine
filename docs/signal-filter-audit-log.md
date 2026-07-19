# Signal Filter audit log

Every decision includes item, stage, decision, machine reason code, explanation, threshold, observed value, configuration version, model version when applicable, and a UTC timestamp. Statuses are deliberately separate: quality rejection, duplicate, review, accepted, and `qualified_but_cut_for_volume`.

Stage errors are redacted to the exception type, route remaining items to review, and do not expose source documents or secrets. Production logging should add request/run IDs, duration, prompt version, token usage, and estimated cost without logging full documents or personal data.
