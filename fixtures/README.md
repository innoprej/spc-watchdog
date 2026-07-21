# Replay fixtures

This tracked directory is reserved for the schema-versioned, deterministic replay fixtures used by judges.

Canonical live runs are first written to the gitignored `runs/` directory. Phase 3 sanitization copies only approved fixtures here after removing absolute paths, usernames, and credentials. Raw or partially sanitized run artifacts must never be committed.
