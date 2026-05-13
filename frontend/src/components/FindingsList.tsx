import { useMemo, useState } from 'react'
import type { Dimension, Finding, Severity } from '../types'
import { RULE_INFO } from '../ruleInfo'

interface Props {
  findings: Finding[]
  // Optional: pass to enable per-finding Fix buttons. Receives the rule_id +
  // target_obj_id; parent owns the catalog + persistence.
  onFix?: (ruleId: string, targetObjId: number) => Promise<void> | void
  onFixAll?: () => Promise<void> | void
  fixing?: boolean             // disables buttons while a fix is in flight
  fixingTarget?: { ruleId: string; targetObjId: number } | null
}

const SEV_BADGE: Record<Severity, string> = {
  info: 'bg-slate-100 text-slate-700 ring-slate-200',
  warn: 'bg-amber-100 text-amber-800 ring-amber-200',
  error: 'bg-orange-100 text-orange-800 ring-orange-200',
  critical: 'bg-red-100 text-red-800 ring-red-200',
}

const SEV_DOT: Record<Severity, string> = {
  critical: 'bg-red-500',
  error: 'bg-orange-500',
  warn: 'bg-amber-400',
  info: 'bg-slate-300',
}

const SEV_ORDER: Record<Severity, number> = {
  critical: 0,
  error: 1,
  warn: 2,
  info: 3,
}

const ALL_SEVS: Severity[] = ['critical', 'error', 'warn', 'info']

export default function FindingsList({
  findings,
  onFix,
  onFixAll,
  fixing = false,
  fixingTarget = null,
}: Props) {
  const [sevFilter, setSevFilter] = useState<Set<Severity>>(new Set())
  const [dimFilter, setDimFilter] = useState<Set<Dimension>>(new Set())
  // Per-finding expanded state, keyed by `${rule_id}::${target_obj_id}` so
  // re-orderings (after a fix changes id ordering) don't accidentally collapse
  // the wrong row.
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const fixableCount = useMemo(
    () => findings.filter((f) => f.fixable).length,
    [findings]
  )

  function toggleExpanded(key: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  // Active dimensions are derived from findings — only show chips for
  // dimensions that actually have findings to filter.
  const presentDims = useMemo(() => {
    const ds = new Set<Dimension>()
    for (const f of findings) ds.add(f.dimension)
    return [...ds].sort()
  }, [findings])

  const filtered = useMemo(() => {
    return findings.filter((f) => {
      if (sevFilter.size > 0 && !sevFilter.has(f.severity)) return false
      if (dimFilter.size > 0 && !dimFilter.has(f.dimension)) return false
      return true
    })
  }, [findings, sevFilter, dimFilter])

  if (findings.length === 0) {
    return (
      <div className="rounded-2xl bg-white border border-slate-200 p-8 text-center shadow-sm">
        <p className="text-slate-500">No findings. Clean model.</p>
      </div>
    )
  }

  const byDim = new Map<string, Finding[]>()
  for (const f of filtered) {
    if (!byDim.has(f.dimension)) byDim.set(f.dimension, [])
    byDim.get(f.dimension)!.push(f)
  }
  for (const arr of byDim.values()) {
    arr.sort((a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity])
  }

  const dims = [...byDim.entries()].sort((a, b) => {
    const worstA = Math.min(...a[1].map((f) => SEV_ORDER[f.severity]))
    const worstB = Math.min(...b[1].map((f) => SEV_ORDER[f.severity]))
    return worstA - worstB
  })

  function toggle<T>(set: Set<T>, val: T): Set<T> {
    const next = new Set(set)
    if (next.has(val)) next.delete(val)
    else next.add(val)
    return next
  }

  const totalShown = filtered.length
  const totalAll = findings.length

  return (
    <div className="rounded-2xl bg-white border border-slate-200 p-6 shadow-sm">
      <div className="flex items-baseline justify-between mb-1 gap-3">
        <h3 className="text-sm font-semibold text-slate-700">
          Findings ({totalShown}{totalShown !== totalAll && <span className="text-slate-400"> / {totalAll}</span>})
        </h3>
        <div className="flex items-center gap-3 shrink-0">
          {(sevFilter.size > 0 || dimFilter.size > 0) && (
            <button
              onClick={() => {
                setSevFilter(new Set())
                setDimFilter(new Set())
              }}
              className="text-xs text-slate-500 hover:text-slate-800 transition-colors"
            >
              Clear filters
            </button>
          )}
          {onFixAll && fixableCount > 0 && (
            <button
              onClick={() => void onFixAll()}
              disabled={fixing}
              className="rounded-md bg-emerald-600 px-3 py-1 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-wait transition-colors shadow-sm"
            >
              {fixing ? 'Fixing…' : `Fix all auto-fixable (${fixableCount})`}
            </button>
          )}
          {onFixAll && fixableCount === 0 && totalAll > 0 && (
            <span
              title="Auto-fix only covers naming rules today (snake_case, max length, reserved words). Other dimensions need manual review."
              className="text-xs text-slate-500 italic"
            >
              No auto-fixes available
            </span>
          )}
        </div>
      </div>
      <p className="text-xs text-slate-500 mb-4">
        Grouped by dimension · sorted by severity
        {fixableCount > 0 && (
          <>
            <span className="mx-1.5 text-slate-300">·</span>
            <span className="text-emerald-700 font-medium">
              {fixableCount} of {totalAll} have a one-click <span className="font-semibold">Fix</span>
            </span>
          </>
        )}
      </p>

      {/* Filter chips */}
      <div className="space-y-2 mb-5">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mr-1">
            Severity
          </span>
          {ALL_SEVS.map((s) => {
            const count = findings.filter((f) => f.severity === s).length
            if (count === 0) return null
            const active = sevFilter.has(s)
            return (
              <button
                key={s}
                onClick={() => setSevFilter(toggle(sevFilter, s))}
                className={`inline-flex items-center gap-1.5 rounded-full pl-2 pr-2.5 py-0.5 text-xs ring-1 transition-colors ${
                  active
                    ? `${SEV_BADGE[s]} font-semibold`
                    : 'bg-white text-slate-600 ring-slate-200 hover:bg-slate-50'
                }`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${SEV_DOT[s]}`} />
                {s} <span className="font-mono opacity-70">{count}</span>
              </button>
            )
          })}
        </div>
        {presentDims.length > 1 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mr-1">
              Dimension
            </span>
            {presentDims.map((d) => {
              const count = findings.filter((f) => f.dimension === d).length
              const active = dimFilter.has(d)
              return (
                <button
                  key={d}
                  onClick={() => setDimFilter(toggle(dimFilter, d))}
                  className={`inline-flex items-center gap-1.5 rounded-full pl-2.5 pr-2.5 py-0.5 text-xs ring-1 transition-colors ${
                    active
                      ? 'bg-amber-100 text-amber-900 ring-amber-200 font-semibold'
                      : 'bg-white text-slate-600 ring-slate-200 hover:bg-slate-50'
                  }`}
                >
                  {d} <span className="font-mono opacity-70">{count}</span>
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* total shown / empty filtering case */}
      {totalShown === 0 ? (
        <p className="text-sm text-slate-400 italic px-2 py-4 text-center">
          No findings match the current filters.
        </p>
      ) : (
        <div className="space-y-2">
          {dims.map(([dim, items]) => (
            <details key={dim} open className="group rounded-lg border border-slate-100">
              <summary className="cursor-pointer select-none flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 rounded-lg">
                <span className="text-xs uppercase tracking-wider font-semibold text-slate-700">
                  {dim}
                </span>
                <span className="text-xs text-slate-400 font-mono">{items.length}</span>
                <svg
                  className="ml-auto h-4 w-4 text-slate-400 transition-transform group-open:rotate-90"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </summary>
              <ul className="border-t border-slate-100">
                {items.map((f, i) => {
                  const isThisFixing =
                    fixing &&
                    fixingTarget?.ruleId === f.rule_id &&
                    fixingTarget?.targetObjId === f.target_obj_id
                  const expandKey = `${f.rule_id}::${f.target_obj_id}`
                  const isOpen = expanded.has(expandKey)
                  return (
                    <li
                      key={i}
                      className="border-t border-slate-100 first:border-t-0"
                    >
                      <div className="flex gap-3 px-4 py-3">
                        <span
                          className={`shrink-0 inline-flex items-center px-2 py-0.5 rounded ring-1 ring-inset text-[10px] font-bold uppercase tracking-wider h-fit mt-0.5 ${SEV_BADGE[f.severity]}`}
                        >
                          {f.severity}
                        </span>
                        <div className="flex-1 min-w-0">
                          {f.target_name && (
                            <p className="text-[11px] font-mono text-slate-500 mb-0.5">
                              {f.target_name}
                            </p>
                          )}
                          <p className="text-sm text-slate-900 leading-relaxed">{f.message}</p>
                          {f.remediation && (
                            <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                              → {f.remediation}
                            </p>
                          )}
                          <div className="mt-1 flex items-center gap-3">
                            <p className="text-[10px] font-mono text-slate-400">{f.rule_id}</p>
                            <button
                              onClick={() => toggleExpanded(expandKey)}
                              className="text-[10px] text-slate-500 hover:text-slate-800 transition-colors inline-flex items-center gap-0.5"
                              aria-expanded={isOpen}
                            >
                              <InfoIcon />
                              {isOpen ? 'Hide details' : 'What does this mean?'}
                            </button>
                          </div>
                        </div>
                        {f.fixable && onFix && (
                          <button
                            onClick={() => void onFix(f.rule_id, f.target_obj_id)}
                            disabled={fixing}
                            title="Apply auto-fix"
                            className="shrink-0 self-start rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-100 disabled:opacity-50 disabled:cursor-wait transition-colors"
                          >
                            {isThisFixing ? 'Fixing…' : 'Fix'}
                          </button>
                        )}
                      </div>
                      {isOpen && (
                        <RuleInfoPanel
                          ruleId={f.rule_id}
                          fixable={f.fixable}
                        />
                      )}
                    </li>
                  )
                })}
              </ul>
            </details>
          ))}
        </div>
      )}
    </div>
  )
}

function InfoIcon() {
  return (
    <svg
      className="h-3 w-3"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  )
}

function RuleInfoPanel({ ruleId, fixable }: { ruleId: string; fixable: boolean }) {
  const info = RULE_INFO[ruleId]
  if (!info) {
    return (
      <div className="px-4 pb-3 pt-1 text-xs text-slate-500 italic">
        No rule info recorded for <code className="font-mono">{ruleId}</code>.
      </div>
    )
  }
  return (
    <div className="mx-4 mb-3 mt-1 rounded-md border border-slate-200 bg-slate-50 p-3 text-xs leading-relaxed space-y-2">
      <Row label="What this checks">{info.summary}</Row>
      {info.impact && <Row label="Why it matters">{info.impact}</Row>}
      {info.fixSummary && (
        <Row label="What the auto-fix does">
          {info.fixSummary}
          {info.examples && info.examples.length > 0 && (
            <ul className="mt-1.5 space-y-0.5">
              {info.examples.map((ex, i) => (
                <li key={i} className="font-mono text-[11px] text-slate-600">
                  <span className="text-slate-400">{ex.before}</span>
                  <span className="mx-1.5 text-emerald-600">→</span>
                  <span className="text-slate-900">{ex.after}</span>
                </li>
              ))}
            </ul>
          )}
        </Row>
      )}
      {!fixable && !info.fixSummary && (
        <Row label="Auto-fix">
          <span className="text-slate-500 italic">
            Not available for this rule — needs manual review.
          </span>
        </Row>
      )}
      <Row label="How to verify">{info.verify}</Row>
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
        {label}
      </p>
      <div className="text-slate-700 mt-0.5">{children}</div>
    </div>
  )
}
