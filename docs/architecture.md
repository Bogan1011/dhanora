# Dhanora architecture

## Decision 001: modular monolith first

React/TypeScript web client -> same-origin Nginx -> FastAPI -> PostgreSQL. One Compose project with a private Docker network and project-scoped persistent volume. Only the web proxy is published, on host loopback by default. DHANORA_BIND_IP may override this for an isolated development network. No database or backend host port. Office development uses CPU only. Optional future AI adapter will call a separate local service on the home GPU; domain operations must not depend on inference.

## Modules and sequencing

Identity and family membership; account and ledger; budgeting and obligations; vehicles; properties and assets; investments; subscriptions; encrypted document vault; local AI/voice; notifications; mobile clients. A module must have API contracts, migration, tests and authorization before exposure.

## Finance invariants

INR amounts are integer paise. Ledger transfers have paired entries and are excluded from income/expense totals. Balance is derived from opening balance and posted entries. Budget recommendations account for future obligations, reserves and remaining days. AI proposes actions; deterministic validation and explicit confirmation precede writes.

## Security boundary

Phase 1 is a development-only skeleton. No user-facing write endpoints. Future sessions use secure cookies, Argon2id, CSRF protection and family-scoped authorization on every request. Membership roles are only database vocabulary at this phase, not working RBAC. Normalize emails before persistence and enforce owner invariants transactionally when implementing identity. Private Tailscale connectivity follows auth; never use public Funnel for family data. Keep secrets and financial records out of Git. Use distinct development and production databases and encrypted backups.

## Reproducibility

Container tags and package ranges are initial development constraints, not immutable release pins. Before release, commit a frontend lockfile and validated Python dependency lock, pin image digests, scan dependencies and test backup/restore.
