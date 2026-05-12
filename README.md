# MetaMart

Mart-Portal-style data model quality scoring platform with a faithful erwin Mart `M70_*` schema on PostgreSQL.

See `PROJECT_PLAN_QualityScore.md` for the design.

## Stack
- Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic
- PostgreSQL 16 + Redis 7 (arq queue + dashboard cache)
- React 18 (frontend, lands in M6)

## Quickstart

Start infrastructure:
```sh
docker compose up -d
```

Install backend:
```sh
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Run migrations:
```sh
alembic upgrade head
```

Seed the database (admin user + Default library + Demo folder + 3 sample catalogs):
```sh
python seed.py
```

Run the API:
```sh
uvicorn metamart.main:app --reload
```

API at http://localhost:8000, docs at http://localhost:8000/docs.

## Tests
```sh
cd backend && pytest
```

## Layout
- `backend/` — FastAPI service + Alembic migrations
  - `src/metamart/mart/` — `M70_*` repository layer
  - `src/metamart/quality/` — scoring engine (M3+)
  - `alembic/versions/` — schema migrations
- `frontend/` — React app (M6+)
- `docker-compose.yml` — Postgres + Redis for local dev

## Milestones
See `PROJECT_PLAN_QualityScore.md` §10. Currently in **M1** (scaffolding + Mart core schema).
