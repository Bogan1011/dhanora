# Dhanora

Your wealth. Your life. Your control.

Dhanora is a local-first, self-hosted personal and family management application. It is under development and is not ready for real financial data.

## Architecture

- React + TypeScript web interface
- FastAPI backend (Python 3.12)
- PostgreSQL with SQLAlchemy and Alembic migrations
- Docker Compose for reproducible development and deployment
- Optional local AI service, isolated from core application operations
- Private remote access through Tailscale after application authentication and authorization are implemented

## Development environments

- CPU-only Ubuntu VM: core application development and testing with mock AI.
- Home GPU server: local inference, speech recognition and integration testing.

## Initial milestone

1. Reproducible container setup and health checks.
2. Database migrations and automated tests.
3. Authentication and family-scoped authorization.
4. Accounts, transaction ledger, budgeting and dashboard.

## Engineering rules

- Store INR monetary values as integer paise, never floating-point amounts.
- Authorize every family-scoped operation on the server.
- Require confirmation and validation before AI-proposed financial mutations.
- Never commit secrets, personal financial records, documents or database backups.
- Keep core functionality available without AI or external services.

## Status

Phase 0: repository and development environment setup. Target: v0.1.0-alpha.
