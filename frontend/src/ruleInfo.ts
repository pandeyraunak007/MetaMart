// Per-rule explanations rendered in the Findings expander, post-fix banner,
// and Audit tab. Kept frontend-side because nothing in the rule registry
// would gain from this metadata being canonical on the backend — it's UX
// content, and the rule_id is a stable contract either way.
//
// Add an entry whenever a new rule lands. Missing entries fall back to a
// generic "no info available" panel; the UI doesn't crash.

export interface RuleInfo {
  /** One-line summary of what the rule checks. */
  summary: string
  /** What the auto-fix does. Omit if the rule has no auto-fix. */
  fixSummary?: string
  /** Short before → after examples for the auto-fix. */
  examples?: { before: string; after: string }[]
  /** Concrete steps the user can take to confirm a fix landed. */
  verify: string
  /**
   * Why the rule matters at all — the impact in production. Optional but
   * useful for the dimensions that aren't auto-fixable, where users need
   * judgement on whether to act.
   */
  impact?: string
}

export const RULE_INFO: Record<string, RuleInfo> = {
  // ── naming ────────────────────────────────────────────────

  'naming.snake_case_physical': {
    summary:
      'Every entity and attribute physical_name must match ^[a-z][a-z0-9_]*$ — lowercase, digits, underscores, starting with a letter.',
    fixSummary:
      "Re-slugs the name: strips uppercase, replaces every non-word character (apostrophe, dash, space, slash, etc.) with '_', collapses runs of underscores.",
    examples: [
      { before: 'CustomerAccount', after: 'customer_account' },
      { before: "customer's email", after: 'customer_s_email' },
      { before: 'mart-fact-orders', after: 'mart_fact_orders' },
    ],
    verify:
      "Re-score the model — the same finding should disappear. In the downloaded JSON, search for the new name; it should appear as the entity's physical_name (native catalog) or the object's Name field + Property 1073742126 (erwin).",
    impact:
      'Mixed-case identifiers behave differently across databases (Postgres folds, SQL Server preserves) and break tooling that assumes a canonical case.',
  },

  'naming.max_length': {
    summary:
      'Physical names should be ≤ 64 characters (configurable via the rule pack).',
    fixSummary:
      'Truncates to "<prefix>_<6-char-sha1>" so two long names that share a prefix stay distinct after truncation.',
    examples: [
      {
        before: 'a_very_long_attribute_name_that_clearly_exceeds_the_default_limit_xx',
        after: 'a_very_long_attribute_name_that_clearly_exceeds_the_default_a3f9d2',
      },
    ],
    verify:
      'Length is now ≤ 64 chars. Re-score and the finding for this target should be gone.',
    impact:
      'Many database engines silently truncate identifiers past their internal limit (Oracle 30 chars pre-12c, others 63/64), which causes mysterious "object not found" errors after deploy.',
  },

  'naming.reserved_word': {
    summary:
      'Names must not be SQL reserved words (select, from, where, user, order, join, table, key, primary, …).',
    fixSummary:
      'Suffixes the name to escape the reserved word: "_tbl" for entities, "_col" for attributes.',
    examples: [
      { before: 'user (entity)', after: 'user_tbl' },
      { before: 'order (attribute)', after: 'order_col' },
    ],
    verify:
      'Search the downloaded JSON for the new name; the suffix should be present. Re-score: the finding is gone.',
    impact:
      'Reserved-word identifiers force every query to quote them (`"user"`), which is easy to forget and breaks ad-hoc SQL written by analysts.',
  },

  // ── normalization ────────────────────────────────────────

  'normalization.repeating_columns': {
    summary:
      'Detects 1NF violations — repeating columns like addr1/addr2/addr3, phone_1/phone_2, that should be a separate child entity.',
    verify:
      'No auto-fix today (a real fix means extracting a child entity, which needs human judgement). To resolve manually: create a new entity (e.g. CustomerAddress), move the repeating columns there with a position field, link via FK.',
    impact:
      "Repeating groups make queries awkward (which slot is 'home'?) and force schema changes whenever you need a fourth instance.",
  },

  'normalization.multi_valued_hint': {
    summary:
      "Flags attribute names that suggest multi-valued storage (e.g. 'tags', 'phone_numbers', 'roles_csv').",
    verify:
      'No auto-fix. To resolve: split into a child entity with one row per value, or use a typed array column if your DB supports them (Postgres TEXT[]).',
    impact:
      'Multi-valued columns block indexing on individual values and break GROUP BY. Costs grow non-linearly with cardinality.',
  },

  // ── orphans ──────────────────────────────────────────────

  'orphans.no_relationships': {
    summary:
      'An entity that has no inbound or outbound FK relationships and no lineage edges.',
    verify:
      'No auto-fix. To resolve: add the missing FK (most common case), wire up lineage if it derives from upstream, OR mark `is_standalone: true` on the entity if it really is reference data.',
    impact:
      "Orphan entities are usually either dead code (legacy table no one removed) or a forgotten relationship. Either way, they break impact-analysis tools that walk the graph.",
  },

  // ── primary keys ─────────────────────────────────────────

  'pks.missing_pk': {
    summary:
      'Every physical entity should have a primary key, unless it is tagged is_view or is_staging.',
    verify:
      "No auto-fix (synthesizing a surrogate key is a real schema decision; better to ask). To resolve: declare the PK in the source model — for erwin, add a Key (XPK...) with the right member attribute. If it's intentionally key-less (a staging or view-like landing zone), set is_view or is_staging on the entity.",
    impact:
      'Without a PK, replication / CDC / dedup all break. Most data tooling assumes one exists.',
  },

  // ── datatypes ────────────────────────────────────────────

  'datatypes.domain_conformance': {
    summary:
      "Attributes whose physical_name matches a known pattern (email, *_at / *_ts, *_date, amount/price/cost/total) should bind to a Domain instead of declaring a raw type, so the type stays consistent across entities.",
    verify:
      "No auto-fix in v1 (we don't know which Domain you'd want). To resolve: define a Domain (e.g. {id: 'd_email', name: 'Email', data_type: 'VARCHAR(320)'}) and reference it from the attribute via the `domain` field.",
    impact:
      "Without Domains, the same logical concept ends up with different types across entities — exactly the source of the cross_entity_consistency errors below.",
  },

  'datatypes.cross_entity_consistency': {
    summary:
      'The same attribute physical_name uses different data types across entities (e.g. `email` is VARCHAR(100) in CUSTOMER but VARCHAR(255) in EMPLOYEE).',
    verify:
      "No auto-fix (we can't pick the canonical type for you). To resolve: pick one type for the concept and update every occurrence — or, better, bind them all to a shared Domain so the change happens in one place.",
    impact:
      'Type drift causes silent truncation when joining tables, makes ETL fail at the boundary, and is the most common root cause of "looked fine in dev" production data bugs.',
  },

  // ── glossary ─────────────────────────────────────────────

  'glossary.entity_uncovered': {
    summary:
      'An entity has no linked GlossaryTerm — there is no business definition explaining what it represents.',
    verify:
      "No auto-fix (writing a definition is human work). To resolve: define a GlossaryTerm in the catalog (e.g. {id: 'g_customer', name: 'Customer', definition: 'Someone who has rented a movie within the past year.'}) and reference it from the entity via `glossary_terms: ['g_customer']`.",
    impact:
      'Untagged entities are invisible to data-discovery tools. Steward leaderboards score zero. Compliance audits flag them.',
  },

  // ── lineage ──────────────────────────────────────────────

  'lineage.missing_inbound': {
    summary:
      'Warehouse-style entities (physical_name starts with mart_/fact_/dim_) should have at least one inbound LineageEdge — i.e. document where the data comes from.',
    verify:
      'No auto-fix. To resolve: add a LineageEdge to the catalog connecting the upstream source to this entity. Column-level edges count for a 60/40 bonus.',
    impact:
      "Without lineage, downstream consumers can't trace data quality issues back to the source. Impact analysis on schema changes becomes impossible.",
  },
}

/**
 * Parse "Renamed entity 'A' → 'B'" / "Truncated attribute 'A' → 'B'" into
 * structured before/after for the post-fix banner. Returns null if the
 * description doesn't fit that shape — caller falls back to the raw string.
 */
export function parseFixDescription(
  description: string
): { verb: string; kind: string; before: string; after: string } | null {
  const m = description.match(
    /^(Renamed|Truncated|Renamed reserved-word) (entity|attribute) '([^']+)' → '([^']+)'/
  )
  if (!m) return null
  return { verb: m[1], kind: m[2], before: m[3], after: m[4] }
}
