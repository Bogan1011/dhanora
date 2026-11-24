"""Interactive one-time local owner setup; no public registration endpoint."""
from getpass import getpass
from email_validator import validate_email, EmailNotValidError
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.db import make_engine
from app.models import User, Family, FamilyMember, AuditLog
from app.security import hash_password

def main():
    engine = make_engine()
    try:
        with Session(engine) as db:
            if db.scalar(select(User.id).limit(1)) is not None:
                raise SystemExit("Setup already completed. No changes made.")
        try:
            email = validate_email(input("Owner email: ").strip(), check_deliverability=False).normalized.casefold()
        except EmailNotValidError as exc:
            raise SystemExit(str(exc))
        name = input("Your display name: ").strip()
        family_name = input("Family workspace name: ").strip()
        if not name or not family_name or len(name) > 120 or len(family_name) > 120:
            raise SystemExit("Names must be 1–120 characters.")
        password = getpass("New password (12–128 characters): ")
        if password != getpass("Confirm password: "):
            raise SystemExit("Passwords do not match.")
        try:
            encoded = hash_password(password)
        except ValueError as exc:
            raise SystemExit(str(exc))
        with Session(engine) as db, db.begin():
            db.execute(text("SELECT pg_advisory_xact_lock(62002002)"))
            if db.scalar(select(User.id).limit(1)) is not None:
                raise SystemExit("Setup already completed. No changes made.")
            user = User(email=email, display_name=name, password_hash=encoded)
            family = Family(name=family_name)
            db.add_all([user, family])
            db.flush()
            db.add(FamilyMember(user_id=user.id, family_id=family.id, role="owner"))
            db.add(AuditLog(event="owner_bootstrapped", user_id=user.id))
        print("Owner and family workspace created successfully.")
    finally:
        engine.dispose()

if __name__ == "__main__":
    main()
