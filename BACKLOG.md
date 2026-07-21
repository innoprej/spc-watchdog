# SPC Watchdog Backlog

This file holds work that does not directly serve the two seeded scenarios, the three-minute demonstration, or the judge quickstart. Reopen an item only when a phase gate proves it is necessary.

## Deferred product breadth

- Support multiple production lines, products, characteristics, subgroups, and chart types.
- Implement Nelson Rules 4–8 and configurable rule variants.
- Add an interactive scenario authoring system instead of fixed seeded manifests.
- Add mobile-specific layouts beyond basic responsive safety.
- Add generalized OCAP authoring, merge-conflict resolution, and rollback UI.

## Deferred operational hardening

- Run concurrent investigators or distribute incident work across a durable queue.
- Add production identity, role-based access control, tenant isolation, and approval delegation.
- Add database migrations across arbitrary historical schema versions.
- Add event-log compaction, long-retention policy, and cross-instance WebSocket recovery.
- Add operating-system-level isolation beyond the smallest sandbox and broker boundary proven by the Phase 1 spike.
- Add production observability, alerting, backup, disaster recovery, and deployment automation.

## Conditional fallback

- Keep `danger-full-access`, WSL/container isolation, and a direct GPT-5.6 API investigation runtime dormant unless the adopted safe-sandbox MCP path later fails a documented live-runtime gate. Do not build or maintain parallel paths speculatively.
