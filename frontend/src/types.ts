export type Severity = 'info' | 'warn' | 'error' | 'critical'

export type Dimension =
  | 'naming'
  | 'normalization'
  | 'orphans'
  | 'pks'
  | 'datatypes'
  | 'glossary'
  | 'lineage'

export interface Finding {
  rule_id: string
  dimension: Dimension
  severity: Severity
  target_obj_id: number
  target_name: string | null
  message: string
  remediation: string | null
  fixable: boolean
}

export interface AppliedFix {
  rule_id: string
  target_obj_id: number
  description: string
}

export interface FixResponse {
  applied: boolean
  description: string
  catalog: unknown
  result: ScanResult
}

export interface FixAllResponse {
  catalog: unknown
  applied: AppliedFix[]
  result: ScanResult
}

export interface SubScore {
  dimension: Dimension
  score: number
  finding_count_by_severity: Record<Severity, number>
  population_size: number
}

export interface ScanResult {
  pack_id: string
  composite_score: number
  grade: string
  sub_scores: SubScore[]
  findings: Finding[]
}

// ── Mart Portal storage shape (localStorage-backed) ──────────

export interface Scan {
  id: string
  scanned_at: string  // ISO timestamp
  result: ScanResult
}

export type AuditEventKind =
  | 'model_created'
  | 'model_renamed'
  | 'model_scored'
  | 'model_deleted'
  | 'folder_created'
  | 'library_created'

export interface AuditEvent {
  id: string
  kind: AuditEventKind
  at: string          // ISO timestamp
  message: string
  // For fix events: the rule_id(s) that were involved. Used to surface the
  // verify hint from RULE_INFO under the audit entry. Optional + backward-
  // compatible with events stored before this field existed.
  rule_ids?: string[]
}

export interface SavedModel {
  id: string
  name: string
  catalog_json: unknown    // raw user-uploaded JSON; replayable through /score-json
  scans: Scan[]            // newest first
  audit: AuditEvent[]      // newest first
  created_at: string
  updated_at: string
}

export interface Folder {
  id: string
  name: string
  models: SavedModel[]
}

export interface Library {
  id: string
  name: string
  folders: Folder[]
  created_at: string
}

export interface MartState {
  libraries: Library[]
  // Schema version — bump when we change the on-disk shape so older clients
  // can wipe-and-reseed instead of crashing on missing fields.
  schema_version: 1
}
