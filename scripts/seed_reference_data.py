"""
Migrates the database to head and fills the reference tables.

Thin CLI over backend/db/provision.py, which the application also runs at
startup -- so the manual and automatic paths cannot drift apart.

Run from the project root, with an active .venv and a running Postgres:
    python scripts/seed_reference_data.py
"""
import os
import sys

from dotenv import load_dotenv

# A script, not a package: the project root has to be on the search path
# before the backend imports, hence the noqa markers on them.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# pylint: disable=wrong-import-position  # sys.path is set up just above
from backend.db.provision import inventory, provision  # noqa: E402
from backend.db.session import session_scope  # noqa: E402


def main() -> None:
    """Provision the database, then print what was created and what is there."""
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    created = provision()
    with session_scope() as db:
        counts = inventory(db)
    print("Created:  ", ", ".join(f"{k} {v}" for k, v in created.items()))
    print("Inventory:", ", ".join(f"{k} {v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
