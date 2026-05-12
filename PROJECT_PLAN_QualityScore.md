# MetaMart Quality — Mart-Portal-Style Model Quality Scoring Platform

A metadata health analytics module that scores every data model on objective dimensions (naming, normalization, orphans, PKs, datatypes, glossary, lineage) and rolls them into a single 0–100 **Model Quality Score**. Built on a Postgres-backed, **erwin Mart-compatible repository schema** (`M70_*` tables) so models, versions, permissions, and audit live where enterprise data-modeling teams already expect them.

---

## 1. Objectives

- Replace subjective "is this model good?" arguments with a **reproducible, defensible score**.
- Make quality issues **actionable**: every score drills down to offending objects with a remediation hint.
- Track **quality over time** at the **model-version** grain — every check-in produces a snapshot, so score moves correlate to a specific commit and author.
- Store metadata in a **faithful erwin Mart schema** so existing Mart dumps can be ingested and erwin-trained admins are at home in the data layer.
- Be **opinionated by default, configurable when needed** — ship with starter rule packs ("Kimball DW", "OLTP", "Lakehouse") that admins tune per library.

Non-goals for v1: auto-fixing models, real-time linting in modeling tools, ML-based anomaly detection, reverse engineering from live databases, multi-tenant deployments.

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    React Mart Portal UI                  │
│   Tree nav (Library → Folder → Model)  │  Tabbed pane   │
└───────────────────────────┬──────────────────────────────┘
                            │  REST /api/v1
┌───────────────────────────┴──────────────────────────────┐
│                     FastAPI Service Layer                │
│  mart.repo │ mart.versioning │ mart.security │ mart.audit │
│  quality.engine │ quality.scoring │ quality.snapshots    │
└───────────────────────────┬──────────────────────────────┘
                            │  SQLAlchemy + Alembic
┌───────────────────────────┴──────────────────────────────┐
│                        PostgreSQL                        │
│  schema: mart    (M70_OBJECT, M70_*, SCD Type 2 specs)   │
│  schema: quality (snapshots, findings, rules, waivers)   │
└──────────────────────────────────────────────────────────┘
                            ▲
                    Redis: arq queue + dashboard cache
```

**Stack:** Python 3.12 / FastAPI / SQLAlchemy 2 (sync) / Alembic / PostgreSQL 16 / React 18 / Recharts. Background scan worker via `arq` (Redis) with single-flight job keys so rapid check-ins coalesce.

**Why Postgres, not SQLite:** Mart's permission model, version tree, polymorphic object/property pattern, and concurrent check-in/check-out semantics need real transactional + row-level guarantees.

---

## 3. Data Model — `mart` Schema (Bitemporal, Hybrid M70_*)

Hybrid storage: **hot properties live as columns on specialization tables**; UDPs and rare properties live in EAV. Version state is captured with **SCD Type 2 range columns** (`version_from`, `version_to`) on every versioned table — no per-version materialization. This is what scales past a few hundred versions per model.

### Versioning pattern

Versioned tables (`m70_entity`, `m70_attribute`, `m70_key`, `m70_property`, `m70_relationship`, etc.) carry a half-open interval `[version_from, version_to)`:
- `version_from BIGINT NOT NULL` — first version this row is valid in.
- `version_to BIGINT NULL` — *first* version the row is no longer valid in (i.e., the version that replaced or deleted it); `NULL` = currently live.
- Composite PK includes `version_from` so the same `obj_id` can have multiple historical rows.

"State of model M at version V":
```sql
WHERE version_from <= V AND (version_to IS NULL OR version_to > V)
```

An edit at version V closes the current row (`UPDATE … SET version_to = V`) and inserts a new row with `version_from = V`. The closing version is the new version itself — no lookup of "previous valid version" needed. Unchanged rows survive across versions for free. All temporal mutations go through `repo.temporal_upsert(obj_id, version_id, **fields)` — never raw UPDATE/INSERT — so the close-then-insert pattern can't be partially applied.

### Identity hub (NOT versioned)

| Table | Purpose |
| --- | --- |
| `M70_OBJECT` | Polymorphic identity row. One row per logical object. `(obj_id, obj_type, parent_obj_id, mart_id, created_by, created_ts, modified_by, modified_ts, is_deleted)`. PK `obj_id`. All cross-table FKs point here. |

`obj_type` is an enum (`LIBRARY`, `FOLDER`, `MODEL`, `SUBJECT_AREA`, `ENTITY`, `ATTRIBUTE`, `KEY`, `KEY_MEMBER`, `RELATIONSHIP`, `DOMAIN`, `GLOSSARY_TERM`, `LINEAGE_EDGE`, `UDP`).

### Hierarchy (administrative, NOT versioned)

| Table | Hot columns |
| --- | --- |
| `M70_LIBRARY` | `obj_id` (PK, FK → m70_object), `name`, `description`, `owner_user_id` |
| `M70_FOLDER` | `obj_id` (PK), `parent_folder_obj_id`, `library_obj_id`, `name` |
| `M70_MODEL` | `obj_id` (PK), `folder_obj_id`, `name`, `model_type` (logical/physical/lp), `description`. **No `current_version_id`** — derived via `v_current_model_version`. |

### Versioning anchor

| Table | Purpose |
| --- | --- |
| `M70_MODEL_VERSION` | `(version_id PK, model_obj_id, version_num, author_user_id, comment, created_ts, is_named, named_label)`. One row per check-in. Unique `(model_obj_id, version_num)`. |
| `M70_LOCK` | Check-out. `(obj_id PK, locked_by_user_id, locked_ts, expires_ts)`. |

**Dropped:** `M70_MODEL_VERSION_OBJECT`. Replaced by `version_from`/`version_to` everywhere.

### Versioned specializations (added in M2.5)

| Table | Hot columns |
| --- | --- |
| `M70_SUBJECT_AREA` | `model_obj_id`, `name`, `description` |
| `M70_ENTITY` | `model_obj_id`, `subject_area_obj_id`, `logical_name`, `physical_name`, `comment`, `is_view`, `is_staging`, `is_standalone` |
| `M70_ATTRIBUTE` | `entity_obj_id`, `logical_name`, `physical_name`, `data_type`, `is_nullable`, `position`, `comment`, `domain_obj_id` |
| `M70_KEY` | `entity_obj_id`, `key_type` (PK/AK/IE), `name` |
| `M70_KEY_MEMBER` | `key_obj_id`, `attribute_obj_id`, `sort_order`, `sort_direction` |
| `M70_RELATIONSHIP_LOGICAL` | `parent_entity_obj_id`, `child_entity_obj_id`, `name`, `cardinality`, `is_identifying` |
| `M70_DOMAIN` | `name`, `data_type`, `default_value`, `check_constraint`, `description` |
| `M70_GLOSSARY_TERM` | `name`, `definition`, `status` |
| `M70_LINEAGE_EDGE` | `source_obj_id`, `target_obj_id`, `transformation_sql` |
| `M70_UDP` | `name`, `value_type` (registry; values land in `M70_PROPERTY`) |

Each: shares `obj_id` with `M70_OBJECT`, carries `version_from`/`version_to`, composite PK `(obj_id, version_from)`. Cross-table FKs reference `M70_OBJECT.obj_id` (the stable identity), not the composite PK.

### EAV for the long tail

| Table | Purpose |
| --- | --- |
| `M70_PROPERTY_DEF` | Catalog of UDP keys. Hot properties live on specialization tables — not here. |
| `M70_PROPERTY` | EAV for UDPs and rare properties only. `(obj_id, prop_id, version_from, version_to, val_string, val_numeric, val_clob, val_blob, val_date)`. Composite PK `(obj_id, prop_id, version_from)`. |
| `M70_RELATIONSHIP` | Typed temporal edges (parentage, FK, lineage). `(rel_id PK, parent_obj_id, child_obj_id, rel_type, seq, version_from, version_to, created_ts)`. SCD2 by app logic on `(parent, child, rel_type)`. |

### Security & audit

| Table | Purpose |
| --- | --- |
| `M70_USER`, `M70_GROUP`, `M70_USER_GROUP` | Standard. |
| `M70_PERMISSION` | `(perm_id, grantee_id, grantee_type, obj_id, perm_mask, granted_by, granted_ts)`. Bitmask: READ, WRITE, DELETE, ADMIN, MANAGE_PERMS, MANAGE_RULES, WAIVE_FINDINGS. Inherited down the folder tree. **v1: grants only — no deny semantics.** |
| `M70_AUDIT_LOG` | `(audit_id, obj_id, action, actor_user_id, ts, details JSONB)`. **Partitioned monthly via pg_partman.** Retention: 7 years. |

### Indexes that matter

- `m70_object(obj_type, parent_obj_id)` — tree walks.
- `m70_property(obj_id, prop_id, version_from)` — property fetch at version.
- `m70_relationship(parent_obj_id, rel_type, version_from)` and `(child_obj_id, rel_type, version_from)` — FK/lineage walks at version.
- Specialization tables: PK `(obj_id, version_from)` covers point lookups; add `(parent_obj_id, version_from)` where the table has a parent FK.

### Convenience views

- `v_current_model_version(model_obj_id, current_version_id, current_version_num)` — replaces the dropped `current_version_id` column.
- `v_entity_at_version(version_id)` — encapsulates the temporal-range filter.

### Schema-fidelity caveat

The M70_* shape is consensus / best-effort. If we get a real erwin Mart export during M1, we patch column names to match. Otherwise the schema is our own erwin-compatible design and any future divergence is a normal migration.

---

## 4. Data Model — `quality` Schema

Sits beside `mart`, FK'd in. Keyed by `(model_obj_id, version_id, pack_id)`.

| Table | Notes |
| --- | --- |
| `quality.rule_pack` | `(pack_id, name, version, weights_json, created_by, created_ts, is_builtin)`. |
| `quality.rule` | `(rule_id, pack_id, dimension, code, severity, params_json, is_enabled)`. |
| `quality.scan` | `(scan_id, model_obj_id, version_id, pack_id, status, triggered_by, started_ts, completed_ts, error_msg, dedupe_key)`. Partial unique on `dedupe_key WHERE status IN ('queued','running')` enforces single-flight. |
| `quality.snapshot` | `(snapshot_id, scan_id, model_obj_id, version_id, pack_id, composite_score, grade, score_naming, score_normalization, score_orphans, score_pks, score_datatypes, score_glossary, score_lineage, is_current, created_ts)`. **Dedicated `score_*` columns (NUMERIC(5,2))**, not JSON. Partial unique `(model_obj_id, version_id, pack_id) WHERE is_current = TRUE` — re-runs flip the previous to false. |
| `quality.finding` | `(finding_id, snapshot_id, rule_id, target_obj_id, severity, message, remediation, signature, is_waived)`. **Partitioned monthly.** |
| `quality.waiver` | `(waiver_id, signature, scope_obj_id, granted_by, granted_ts, expires_ts, justification)`. |
| `quality.mv_portfolio_score` | **Materialized view** over `quality.snapshot WHERE is_current`. Refreshed `CONCURRENTLY` by a nightly cron + after large scan bursts. |

---

## 5. Scoring Methodology

Each check produces **findings**: `(rule_id, severity, target_obj_id, message, remediation_hint)`. Severity `info|warn|error|critical` with weights `0/1/3/10`.

Sub-score per dimension:
```
sub_score = 100 × (1 − Σ(severity_weight × finding_count) / max_possible_penalty)
```
Clamped `[0, 100]`. `max_possible_penalty` scales with the population checked.

**Composite Model Quality Score:** weighted average across dimensions; geometric mean is a per-pack option. Default weights:

| Dimension | Default weight |
| --- | --- |
| Naming consistency | 15 |
| Normalization quality | 15 |
| Orphan tables | 10 |
| Missing PKs | 15 |
| Datatype violations | 15 |
| Glossary coverage | 15 |
| Lineage completeness | 15 |

Grade: A (90+) · B (80–89) · C (70–79) · D (60–69) · F (<60).

Waivers: an actively-waived finding doesn't contribute to penalty but is logged with `is_waived=true` for audit visibility.

---

## 6. The Seven Dimensions

**Naming consistency.** Default `snake_case` physical, `PascalCase` logical. Case style, max length, reserved-word avoidance, approved-abbreviation list, singular/plural for entities, cross-model name drift.

**Normalization quality.** Automatable proxies — 1NF repeating-column detection (`addr1`/`addr2`/`addr3`), multi-valued name hints; 2NF/3NF validation against explicit FD annotations stored as UDPs; heuristic warnings on composite-PK tables with suspicious non-key columns. BCNF opt-in.

**Orphan tables.** Zero inbound + zero outbound FK + zero lineage. Excludes reference tables and `is_standalone=true`.

**Missing PKs.** Every physical entity declares a PK unless tagged `view`/`staging`.

**Datatype violations.** Domain conformance (attrs that should bind to a Domain but use raw types) + cross-model type consistency.

**Glossary coverage.** % of entities/attributes linked to ≥1 GLOSSARY_TERM. Entities 2×, attributes 1×. `technical`/`staging` excluded.

**Lineage completeness.** Fraction of `mart`/`fact`/`dim` entities with ≥1 inbound LINEAGE_EDGE; column-level bonus combined 60/40.

---

## 7. Versioning, Permissions & Audit

**Check-in flow.**
1. Modeler checks out → `M70_LOCK` row.
2. Edits stage in a workspace (in-memory in v1; persistent `m70_workspace` shadow table is TBD in M2).
3. On check-in:
   - INSERT `M70_MODEL_VERSION` → get `version_id` V.
   - For each *added* object: INSERT into m70_object + specialization with `version_from = V`.
   - For each *removed* object: UPDATE matching live row `version_to = V - 1`.
   - For each *changed* object: UPDATE old row `version_to = V - 1`; INSERT new row with `version_from = V`.
   - INSERT `M70_AUDIT_LOG` row.
   - Release lock.
4. Webhook fires → `arq` enqueues with job key `scan:{model_id}:{version_id}:{pack_id}` (single-flight).
5. Worker writes scan + snapshot + findings; flips previous current snapshot to `is_current=false`.
6. Worker invalidates Redis keys `dashboard:model:{id}` and `dashboard:portfolio`.

**SLO.** p95 time-to-score after check-in ≤ 30s for models ≤ 10k objects.

**Permission inheritance.** Effective perms = OR of all ancestor grants for the user + their groups. v1 is grants-only.

**Audit annotations.** Trend charts surface `M70_AUDIT_LOG` author + comment on hover. Score drops between v17 → v18 read: "jdoe — 'denormalize orders'".

**Compare versions.** `GET /mart/models/{id}/versions/{v1}/compare/{v2}` returns temporal-range diff + quality delta per dimension.

---

## 8. Dashboard — Mart Portal Shell

Tree nav left (Library → Folder → Folder → Model), tabbed content right: **Overview · Objects · Versions · Security · Audit · Quality · Reports**.

- **Portfolio view (`/quality`).** Big number + sortable table per model with score, grade, trend arrow, worst-offender dimension. Folder/library rollups. Driven by `quality.mv_portfolio_score`.
- **Model Quality tab.** Score + grade + 30-version sparkline. Seven-dim radar. Findings collapsed by dimension with severity badges, deep links, remediation tooltips. "Waived" sub-tab.
- **Trends.** Version-axis time series of composite + per-dimension. Multi-model overlay. Audit annotations on hover.
- **Compare Versions.** v1 vs v2 side-by-side: dimension deltas, new/resolved/still-open findings.
- **Rules admin.** Pack browser, rule toggle, weight editor, **impact preview** ("turning off rule X moves portfolio avg 78 → 82"). Packs are versioned.
- **Reports.** CSV / Markdown / PDF. Quality Brief PDF signed by `MANAGE_RULES` holder.

---

## 9. API Surface (v1)

REST under `/api/v1`, OpenAPI at `/docs`.

**Mart repository.**
- `GET /mart/libraries` · `GET /mart/libraries/{id}` · `POST /mart/libraries`
- `GET /mart/folders/{id}/children`
- `GET /mart/models/{id}` · `POST /mart/models/{id}/checkout` · `POST /mart/models/{id}/checkin`
- `GET /mart/models/{id}/versions` · `GET /mart/models/{id}/versions/{v}`
- `GET /mart/objects/{obj_id}` · `GET /mart/objects/{obj_id}/properties?at_version=`
- `GET /mart/objects/{obj_id}/audit`
- `GET|PUT /mart/permissions?obj_id=...`

**Quality.**
- `POST /quality/scan` — `{model_obj_id, version_id?, pack_id?}`. Async. Returns `202` with `{scan_id, dedupe_key, status}`. If the dedupe_key matches an in-flight scan, returns its scan_id (single-flight).
- `GET /quality/scans/{id}`
- `GET /quality/snapshots/latest?scope=library&id=...`
- `GET /quality/models/{id}/versions/{v}/score`
- `GET /quality/models/{id}/versions/{v1}/compare/{v2}`
- `GET /quality/findings?model_id=&dimension=&severity=&page=`
- `GET|PUT /quality/rules` · `GET|POST /quality/rule-packs`
- `POST /quality/waivers`
- `GET /quality/reports/quality-brief.pdf?model_id=&version=`

**Webhooks.**
- `POST /hooks/mart/checkin` — internal, enqueues scan.

Dashboard read endpoints return `ETag` and `Cache-Control: max-age=300`.

---

## 10. Milestones & Timeline

Single engineer. ~4.5 weeks.

**M1 — Postgres scaffolding + Mart core schema (5 days).** Alembic migration for the identity hub + hierarchy + versioning + security + audit (no entity/attribute specializations yet). SQLAlchemy mappers. Library/Folder/Model REST CRUD with a permission stub. Docker Compose for Postgres + Redis. Smoke tests.

**M2 — Versioning, locking, audit (3 days).** Check-out/check-in flow. Workspace pattern. `temporal_upsert` helper. Audit-log writes on every mutation. Permission middleware (FastAPI dependency) enforcing inheritance.

**M2.5 — Catalog ingest + entity/attribute specializations (3 days).** Second migration for `m70_subject_area`, `m70_entity`, `m70_attribute`, `m70_key`, `m70_key_member`, `m70_relationship_logical`, `m70_domain`, `m70_glossary_term`, `m70_lineage_edge`, `m70_udp`. JSON-catalog importer + a realistic seed (Northwind + a denormalized warehouse + a greenfield model with intentional violations) so M3+ have real data to score.

**M3 — Rules engine + scoring math (3 days).** Plugin-style rule registry, severity weights, sub-score and composite math, geometric-mean option. Unit tests against the seeded fixtures.

**M4 — The seven default rules (4 days).** "Default" rule pack covering all seven dimensions, pass/fail/edge-case tests each.

**M5 — Scan worker + snapshot persistence (2.5 days).** `arq` worker, single-flight dedupe, scan + snapshot + findings writes, waiver application, Redis cache invalidation. Worker runbook.

**M6 — Mart Portal UI shell (4 days).** Tree nav, tabbed model view, Overview/Versions/Audit tabs against real data. Auth wiring.

**M7 — Quality tab + portfolio view (3 days).** Radar + sparkline + findings drill-down. Portfolio table driven by `quality.mv_portfolio_score`.

**M8 — Compare, trends, rule admin (3 days).** Version compare view, version-axis trend chart with audit annotations, rule pack editor with impact preview.

**M9 — Reports, retention, polish (2 days).** CSV / Markdown / PDF export, Quality Brief, pg_partman partitioning for `m70_audit_log` and `quality.finding`, retention janitor, README, screenshots.

**Total: ~4.5 weeks.**

---

## 11. Integration with MetaMart

This module *replaces* MetaMart's prior SQLite/JSON catalog with the Mart-style Postgres repo. MetaMart's existing UI bolts onto the Mart Portal shell as additional tabs. A migration tool reads the legacy JSON catalog into `M70_*` rows so existing demo data survives. If we later interop with a real erwin Mart deployment, the faithful schema makes a bidirectional replay tractable.

---

## 12. Risks & Mitigations

- **Schema drift vs real erwin Mart.** *Mitigation:* M1 validates against a real Mart dump if available; otherwise the schema is our consensus design and divergence is treated as a normal migration.
- **Temporal-write complexity.** Bitemporal updates are 2 SQL ops; forgetting to close the old row is silent corruption. *Mitigation:* all mutations through `repo.temporal_upsert()` with tests covering insert/update/delete paths. No raw UPDATE/INSERT against versioned tables outside the helper.
- **Score gaming.** *Mitigation:* version-grained diffing, grade-boundary sign-off, transparent weights.
- **False positives on heuristics.** *Mitigation:* signed waivers with justification + expiry, audit-tracked.
- **Subjectivity of "good".** *Mitigation:* 2–3 starter packs; admins fork.
- **Performance on big catalogs.** *Mitigation:* indexed temporal queries, parallel rule execution, `is_current` partial indexes, materialized portfolio view, Redis cache on dashboard reads (TTL 5 min).
- **Postgres operational overhead.** *Mitigation:* Docker Compose ships in-repo; pool_size=20 / max_overflow=20 per worker; pgbouncer optional past ~100 concurrent.
- **Lock leaks.** *Mitigation:* `M70_LOCK.expires_ts` enforced by janitor.
- **Audit / finding table growth.** *Mitigation:* monthly partitioning via pg_partman. Audit retention 7 years; finding retention tied to snapshot retention (3 years live + 7 years archived).
- **Scan worker runbook gaps.** *Mitigation:* M5 ships with a runbook (stuck-scan triage, snapshot replay, force-rescan a portfolio). Alert on scan failure rate > 5%/hr.

---

## 13. Why This Lands With Enterprise Buyers

- A single number data leaders put on a slide alongside DORA / SLA metrics.
- Plays into DAMA / DCAM governance programs.
- Trend view makes ROI on data-modeling investment **visible**.
- Rule packs meet an org where they are.
- **erwin Mart parity at the data layer** means existing erwin shops see a credible upgrade path, not a rip-and-replace.

---

## 14. Roadmap (Post-MVP)

- Native erwin Mart import/export (binary `.erwin` model parsing).
- ML-assisted naming suggestions.
- SQL/dbt parsing for FD violation auto-detection.
- "Steward leaderboard."
- Slack/Teams alerts on grade changes.
- Policy-as-code: rule packs in Git; CI gate.
- Cross-org anonymized benchmarks.
- **Multi-tenancy** — `tenant_id` migration with row-level security policies.
- **Permission denies** — explicit revocation in `M70_PERMISSION`.
- **System-versioned temporal extension** — evaluate Postgres `temporal_tables` ext to replace manual range columns.

---

## 15. Decisions Still Open

- **Composite formula default** — weighted average vs geometric mean. Default: weighted average; geometric is a per-pack toggle.
- **Waivers and the score** — count at reduced weight, or zero out entirely? Default: zero, but `is_waived` findings still appear in reports.
- **Scan cadence** — on every check-in (default) + nightly full rescans.
- **Workspace storage during check-out** — in-memory client vs shadow `m70_workspace` table. TBD in M2.
