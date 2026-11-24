# Foundation acceptance checklist

From repository root, create .env with a generated password (never commit it). For isolated VMware access set DHANORA_BIND_IP to the VM private IP; leave loopback for SSH forwarding. Replace 127.0.0.1 in the curl commands below with the configured bind address. Then then run docker compose config --quiet and docker compose up -d --build --wait --wait-timeout 180.

- docker compose ps: database and backend healthy, frontend running.
- curl -fsS http://127.0.0.1:18080/health: status ok.
- curl -fsS http://127.0.0.1:18080/ready: ready, connected, 0001_identity.
- curl -fsS http://127.0.0.1:18080/api/v1/status: AI disabled.
- docker compose exec -T backend alembic current: 0001_identity (head).
- docker compose exec -T backend alembic check: no new upgrade operations.
- docker compose exec -T backend pytest -q: three tests pass.
- docker compose exec -T database psql -U dhanora -d dhanora -c '\dt': users, families, family_members, alembic_version.
- Browser via SSH local port forwarding: dashboard displays system ready and no fabricated financial balances.
- Existing unrelated Compose projects remain running.

Do not expose the application or enter real financial data. Do not run docker compose down -v unless deliberately discarding this project's database. Run docker compose logs --tail=80 on failure; redact secrets before sharing.
