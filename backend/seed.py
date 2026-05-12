"""Seed script: create an admin user, default library, demo folder, and import
the sample catalogs from `backend/seed_data/`.

Usage (with the venv active and Postgres up + migrations applied):

    cd backend
    python seed.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from metamart.db import get_session_factory
from metamart.mart import repo
from metamart.mart.ingest import ingest_catalog

SEED_DIR = Path(__file__).parent / "seed_data"
SEEDS = ["northwind.json", "warehouse_messy.json", "greenfield.json"]


def run() -> int:
    SessionLocal = get_session_factory()
    db: Session = SessionLocal()
    try:
        existing_users = repo.list_users(db)
        if existing_users:
            user = existing_users[0]
            print(f"using existing user '{user.username}' (id={user.user_id})")
        else:
            user = repo.create_user(
                db,
                username="admin",
                display_name="Admin",
                email="admin@metamart.local",
            )
            db.flush()
            print(f"created admin user '{user.username}' (id={user.user_id})")

        libs = repo.list_libraries(db)
        library = next((lib for lib in libs if lib.name == "Default"), None)
        if library is None:
            library = repo.create_library(
                db,
                name="Default",
                description="Default library for demos",
                creator_user_id=user.user_id,
            )
            print(f"created library '{library.name}' (obj_id={library.obj_id})")
        else:
            print(f"using existing library '{library.name}' (obj_id={library.obj_id})")

        roots = repo.list_library_root_folders(db, library.obj_id)
        folder = next((f for f in roots if f.name == "Demo"), None)
        if folder is None:
            folder = repo.create_folder(
                db,
                name="Demo",
                library_obj_id=library.obj_id,
                parent_folder_obj_id=None,
                creator_user_id=user.user_id,
            )
            print(f"created folder '{folder.name}' (obj_id={folder.obj_id})")
        else:
            print(f"using existing folder '{folder.name}' (obj_id={folder.obj_id})")

        db.commit()

        for fname in SEEDS:
            path = SEED_DIR / fname
            if not path.exists():
                print(f"WARN: seed file missing: {path}", file=sys.stderr)
                continue
            print(f"importing {fname} ...")
            with path.open() as fh:
                catalog = json.load(fh)
            model = ingest_catalog(
                db,
                catalog=catalog,
                library_obj_id=library.obj_id,
                folder_obj_id=folder.obj_id,
                author_user_id=user.user_id,
            )
            db.commit()
            print(f"  → model obj_id={model.obj_id} name='{model.name}'")

        print("seed complete.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(run())
