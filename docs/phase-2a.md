# Phase 2A — Identity and sessions

Development only. Bind frontend to loopback (DHANORA_BIND_IP=127.0.0.1), set DHANORA_ORIGIN=http://localhost:18080, and access from Windows through an authenticated SSH local port forward. Modern browsers allow Secure cookies for localhost; if the browser rejects them, configure trusted HTTPS rather than weakening the cookie. Never use direct LAN HTTP for credentials.

Run docker compose up -d --build --wait --wait-timeout 180, then docker compose exec backend python -m app.bootstrap. Use disposable development credentials. Password is entered interactively, not in command history. Bootstrap refuses a second owner once a user exists; no public registration endpoint. Initial owner belongs to the first family only.

Verify readiness revision 0002_authentication, alembic check and pytest. Browser: login succeeds, refresh preserves session, logout revokes it, refresh shows login, incorrect credentials rejected, direct IP and foreign-origin POST rejected. Family selection shows only the signed-in user's memberships. No invitations or financial writes yet.

Session tokens are random and stored hashed, expire after 12 hours, and use Secure HttpOnly SameSite=Strict cookies. Origin checks protect POST routes. Login limits: 5 attempts per email and 30 globally per five minutes (fixed windows); global throttling can temporarily deny legitimate logins and is intended for a small private deployment. Audit records login success/failure, logout and owner bootstrap. Future work: invitation flow, permission checks on domain operations, session list/revocation, audit UI, retention and trusted HTTPS production configuration.
