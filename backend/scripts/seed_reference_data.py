"""Migrate and seed by hand, the same `provision()` the app runs at startup."""
from shared.db.session import session_scope
from backend.db.provision import inventory, provision


def main() -> None:
    created = provision()
    with session_scope() as db:
        counts = inventory(db)
    print("Created:  ", ", ".join(f"{k} {v}" for k, v in created.items()))
    print("Inventory:", ", ".join(f"{k} {v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
