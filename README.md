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

## Score your own model

Three paths, all using the Default rule pack, all no-DB.

**Web UI** (recommended) — drag-drop or paste JSON, see grade + radar + findings:
```sh
# Terminal 1 — backend
cd backend && source .venv/bin/activate
uvicorn metamart.main:app --reload

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```
Then open http://localhost:5173. The Vite dev server proxies `/api/*` to the backend at `:8000`.

**CLI** (prints to stdout):
```sh
cd backend
python score.py path/to/your_model.json
```

**API**:
```sh
curl -s -X POST http://localhost:8000/api/v1/quality/score-json \
  -H "Content-Type: application/json" \
  -d @path/to/your_model.json | jq
```

**JSON format** — same shape as `backend/seed_data/*.json`. Minimum:

```jsonc
{
  "name": "My Model",
  "model_type": "physical",            // logical | physical | lp
  "domains": [                          // optional
    {"id": "d_email", "name": "Email", "data_type": "VARCHAR(320)"}
  ],
  "glossary": [                         // optional
    {"id": "g_customer", "name": "Customer",
     "definition": "Someone who buys things.", "status": "approved"}
  ],
  "entities": [
    {
      "id": "e_customer",
      "logical_name": "Customer",
      "physical_name": "customer",
      "glossary_terms": ["g_customer"],
      "attributes": [
        {"id": "a1", "logical_name": "Customer Id",
         "physical_name": "customer_id", "data_type": "BIGINT",
         "is_nullable": false, "position": 1},
        {"id": "a2", "logical_name": "Email",
         "physical_name": "email", "data_type": "VARCHAR(320)",
         "domain": "d_email", "is_nullable": false, "position": 2}
      ],
      "keys": [
        {"id": "k1", "name": "pk_customer", "key_type": "PK", "members": ["a1"]}
      ]
    }
  ],
  "relationships": [                    // optional
    {"id": "r1", "name": "customer_orders",
     "parent": "e_customer", "child": "e_order",
     "cardinality": "one_to_many", "is_identifying": false}
  ],
  "lineage": []                         // optional
}
```

`id` strings are local references inside the JSON — used by `keys.members`, `relationships.parent/child`, `lineage.source/target`, etc. They don't need to be globally unique.

## Tests
```sh
cd backend && pytest
```

## Deploy to Vercel (quality demo)

The `/quality/score-json` endpoint is stateless, so the upload-and-score demo runs on Vercel's free tier. The `mart/*` surface (libraries, check-in/out, permissions) needs Postgres and is not part of the Vercel deployment.

**One-click via GitHub:**
1. Push this repo to GitHub (already done at https://github.com/pandeyraunak007/MetaMart).
2. Open https://vercel.com/new, import the repo, and click Deploy.
3. Vercel reads `vercel.json` at the repo root and:
   - builds the frontend from `frontend/` (`npm ci && npm run build` → `frontend/dist`),
   - bundles `api/index.py` + `backend/src/` as a Python serverless function,
   - rewrites `/api/*` → the function, serves everything else statically.
4. Public URL like `https://metamart-<your-handle>.vercel.app` once the build finishes.

**CLI (if you have `vercel` installed):**
```sh
npm i -g vercel
vercel              # first run: link to a Vercel project
vercel --prod       # ship it
```

The frontend's `api.ts` calls `/api/v1/quality/score-json` as a same-origin path — works in dev (Vite proxy → :8000) and prod (Vercel rewrite → serverless function) with no code changes.

## Layout
- `backend/` — FastAPI service + Alembic migrations
  - `src/metamart/mart/` — `M70_*` repository layer
  - `src/metamart/quality/` — scoring engine (M3+)
  - `alembic/versions/` — schema migrations
- `frontend/` — React app (M6+)
- `docker-compose.yml` — Postgres + Redis for local dev

## Milestones
See `PROJECT_PLAN_QualityScore.md` §10. Currently in **M1** (scaffolding + Mart core schema).
