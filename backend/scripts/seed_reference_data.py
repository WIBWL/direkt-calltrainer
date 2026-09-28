"""Migrates the database to head and fills the reference tables -- a thin CLI over
backend/db/provision.py, which the app also runs at startup.

Run from the project root with .env sourced and the database running:
    python -m backend.scripts.seed_reference_data"""
from shared.db.session import session_scope
from backend.db.provision import inventory, provision


def main() -> None:
    """Provision the database, then print what was created and what is there."""
    created = provision()
    with session_scope() as db:
        counts = inventory(db)
    print("Created:  ", ", ".join(f"{k} {v}" for k, v in created.items()))
    print("Inventory:", ", ".join(f"{k} {v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
