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
  message: string
  remediation: string | null
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
