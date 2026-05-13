import { useMemo, useState } from 'react'
import type {
  Dimension,
  Finding,
  SavedModel,
  Scan,
  ScanResult,
  Severity,
  SubScore,
} from '../types'

interface Props {
  model: SavedModel
}

const SEV_ORDER: Record<Severity, number> = {
  critical: 0,
  error: 1,
  warn: 2,
  info: 3,
}

const SEV_BADGE: Record<Severity, string> = {
  info: 'bg-slate-100 text-slate-700 ring-slate-200',
  warn: 'bg-amber-100 text-amber-800 ring-amber-200',
  error: 'bg-orange-100 text-orange-800 ring-orange-200',
  critical: 'bg-red-100 text-red-800 ring-red-200',
}

const GRADE_TEXT: Record<string, string> = {
  A: 'text-emerald-700',
  B: 'text-lime-700',
  C: 'text-amber-700',
  D: 'text-orange-700',
  F: 'text-red-700',
}

interface DiffEntry {
  rule_id: string
  dimension: Dimension
  target_name: string
  before?: Finding
  after?: Finding
}

interface DiffResult {
  resolved: DiffEntry[]
  added: DiffEntry[]      // 'new' shadows the JS keyword
  changed: DiffEntry[]    // severity changed
  unchanged: DiffEntry[]
}

export default function CompareTab({ model }: Props) {
  // Scans are stored newest-first in the model. Default A (older baseline) =
  // last entry; default B (latest) = first entry. Picking A == B is allowed
  // and just shows a no-op diff — useful when sanity-checking a single scan.
  const [aId, setAId] = useState<string>(
    () => model.scans[model.scans.length - 1]?.id ?? ''
  )
  const [bId, setBId] = useState<string>(
    () => model.scans[0]?.id ?? ''
  )
  const [showUnchanged, setShowUnchanged] = useState(false)

  if (model.scans.length < 2) {
    return (
      <div className="max-w-3xl rounded-2xl border border-dashed border-slate-200 bg-white/40 p-10 text-center">
        <p className="text-base font-medium text-slate-700">Need at least 2 scans</p>
        <p className="mt-2 text-sm text-slate-500">
          Re-score this model (or apply a fix) and come back here to see what
          changed between any two scans.
        </p>
      </div>
    )
  }

  const a = model.scans.find((s) => s.id === aId) ?? model.scans[model.scans.length - 1]
  const b = model.scans.find((s) => s.id === bId) ?? model.scans[0]

  const diff = useMemo(() => computeDiff(a.result, b.result), [a, b])
  const dimDeltas = useMemo(() => computeDimensionDeltas(a.result, b.result), [a, b])
  const compositeDelta = b.result.composite_score - a.result.composite_score

  const sameScan = a.id === b.id

  return (
    <div className="max-w-5xl space-y-6">
      {/* Scan pickers */}
      <div className="rounded-2xl bg-white border border-slate-200 p-5 shadow-sm">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">
          Compare two scans
        </p>
        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-4 items-end">
          <ScanPicker
            label="A (baseline)"
            value={a.id}
            scans={model.scans}
            latestId={model.scans[0]?.id}
            onChange={setAId}
          />
          <div className="flex items-center justify-center text-slate-400 pb-2">
            <ArrowRight />
          </div>
          <ScanPicker
            label="B (after)"
            value={b.id}
            scans={model.scans}
            latestId={model.scans[0]?.id}
            onChange={setBId}
          />
        </div>
      </div>

      {sameScan ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500 italic">
          Same scan selected on both sides. Pick a different scan for B to see
          a diff.
        </div>
      ) : (
        <>
          <DeltaHeader
            a={a}
            b={b}
            compositeDelta={compositeDelta}
            dimDeltas={dimDeltas}
            netResolved={diff.resolved.length}
            netAdded={diff.added.length}
          />

          <DiffSection
            title="Resolved"
            tone="emerald"
            description="In A, gone in B — usually because of a fix or the violating object was removed."
            entries={diff.resolved}
            renderEntry={(e) => (
              <DiffRow
                primary={e.before!}
                muted={false}
              />
            )}
          />

          <DiffSection
            title="New"
            tone="red"
            description="In B, not in A — newly introduced findings since the baseline."
            entries={diff.added}
            renderEntry={(e) => (
              <DiffRow primary={e.after!} muted={false} />
            )}
          />

          <DiffSection
            title="Severity changed"
            tone="amber"
            description="Same target + rule, but the severity moved between scans (rule pack tuning, or the violation got more / less serious)."
            entries={diff.changed}
            renderEntry={(e) => (
              <DiffRowChanged before={e.before!} after={e.after!} />
            )}
          />

          {/* Unchanged is hidden behind a toggle to keep the diff focused. */}
          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            <button
              onClick={() => setShowUnchanged(!showUnchanged)}
              className="w-full px-5 py-3 flex items-center justify-between hover:bg-slate-50 text-left"
            >
              <span className="text-sm font-semibold text-slate-700">
                Unchanged
                <span className="ml-2 text-xs font-mono text-slate-400">
                  {diff.unchanged.length}
                </span>
              </span>
              <span className="text-xs text-slate-500">
                {showUnchanged ? 'Hide' : 'Show'}
              </span>
            </button>
            {showUnchanged && (
              <div className="border-t border-slate-100">
                {diff.unchanged.length === 0 ? (
                  <p className="px-5 py-4 text-sm text-slate-400 italic">
                    No findings appear in both scans.
                  </p>
                ) : (
                  <ul>
                    {sortByDimSeverity(diff.unchanged).map((e, i) => (
                      <li
                        key={i}
                        className="px-5 py-3 border-t border-slate-100 first:border-t-0"
                      >
                        <DiffRow primary={e.before!} muted />
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// ── header strip ─────────────────────────────────────────────

function DeltaHeader({
  a,
  b,
  compositeDelta,
  dimDeltas,
  netResolved,
  netAdded,
}: {
  a: Scan
  b: Scan
  compositeDelta: number
  dimDeltas: Array<{ dimension: Dimension; a: number; b: number; delta: number }>
  netResolved: number
  netAdded: number
}) {
  const aGrade = a.result.grade
  const bGrade = b.result.grade
  const gradeChanged = aGrade !== bGrade
  const tone =
    compositeDelta > 0.01
      ? 'emerald'
      : compositeDelta < -0.01
        ? 'red'
        : 'slate'
  const toneStyles = {
    emerald: 'bg-emerald-50 border-emerald-200 text-emerald-900',
    red: 'bg-red-50 border-red-200 text-red-900',
    slate: 'bg-slate-50 border-slate-200 text-slate-700',
  }[tone]

  return (
    <div className={`rounded-2xl border-2 p-6 shadow-sm ${toneStyles}`}>
      <div className="flex items-baseline gap-6 flex-wrap">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider opacity-70">
            Composite delta
          </p>
          <p className="text-4xl font-bold tabular-nums mt-0.5">
            {compositeDelta > 0 ? '+' : ''}
            {compositeDelta.toFixed(2)}
          </p>
          <p className="text-xs mt-1 opacity-80 tabular-nums">
            {a.result.composite_score.toFixed(2)} → {b.result.composite_score.toFixed(2)}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider opacity-70">
            Grade
          </p>
          <p className="text-3xl font-bold mt-0.5 flex items-baseline gap-2">
            <span className={GRADE_TEXT[aGrade] ?? ''}>{aGrade}</span>
            <span className="opacity-60 text-xl">→</span>
            <span className={GRADE_TEXT[bGrade] ?? ''}>{bGrade}</span>
          </p>
          <p className="text-xs mt-1 opacity-80">
            {gradeChanged ? 'changed' : 'unchanged'}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider opacity-70">
            Findings
          </p>
          <p className="text-3xl font-bold tabular-nums mt-0.5 flex items-baseline gap-3">
            <span className="text-emerald-700">−{netResolved}</span>
            <span className="text-red-700">+{netAdded}</span>
          </p>
          <p className="text-xs mt-1 opacity-80 tabular-nums">
            {a.result.findings.length} → {b.result.findings.length}
          </p>
        </div>
      </div>
      <div className="mt-4 pt-4 border-t border-current/20">
        <p className="text-[10px] font-semibold uppercase tracking-wider opacity-70 mb-2">
          By dimension
        </p>
        <div className="flex flex-wrap gap-1.5">
          {dimDeltas.map((d) => (
            <DimDeltaChip key={d.dimension} {...d} />
          ))}
        </div>
      </div>
    </div>
  )
}

function DimDeltaChip({
  dimension,
  a,
  b,
  delta,
}: {
  dimension: string
  a: number
  b: number
  delta: number
}) {
  const tone =
    delta > 0.01
      ? 'bg-emerald-100 text-emerald-900 ring-emerald-200'
      : delta < -0.01
        ? 'bg-red-100 text-red-900 ring-red-200'
        : 'bg-white text-slate-600 ring-slate-200'
  const sign = delta > 0 ? '+' : ''
  return (
    <span
      title={`${dimension}: ${a.toFixed(2)} → ${b.toFixed(2)}`}
      className={`inline-flex items-center gap-1.5 rounded-full pl-2.5 pr-2 py-0.5 text-xs ring-1 ${tone}`}
    >
      <span className="capitalize">{dimension}</span>
      <span className="font-mono font-semibold tabular-nums">
        {Math.abs(delta) < 0.01 ? '0' : `${sign}${delta.toFixed(1)}`}
      </span>
    </span>
  )
}

// ── diff sections ────────────────────────────────────────────

function DiffSection({
  title,
  tone,
  description,
  entries,
  renderEntry,
}: {
  title: string
  tone: 'emerald' | 'red' | 'amber'
  description: string
  entries: DiffEntry[]
  renderEntry: (e: DiffEntry) => React.ReactNode
}) {
  const ringTone =
    tone === 'emerald'
      ? 'border-emerald-200'
      : tone === 'red'
        ? 'border-red-200'
        : 'border-amber-200'
  const headerTone =
    tone === 'emerald'
      ? 'text-emerald-800'
      : tone === 'red'
        ? 'text-red-800'
        : 'text-amber-800'

  return (
    <div className={`rounded-2xl bg-white border-2 ${ringTone} shadow-sm overflow-hidden`}>
      <div className="px-5 py-3 border-b border-slate-100">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className={`text-sm font-bold ${headerTone}`}>
            {title}
            <span className="ml-2 text-xs font-mono text-slate-500">
              {entries.length}
            </span>
          </h3>
        </div>
        <p className="text-xs text-slate-500 mt-0.5">{description}</p>
      </div>
      {entries.length === 0 ? (
        <p className="px-5 py-4 text-sm text-slate-400 italic">
          None.
        </p>
      ) : (
        <ul>
          {sortByDimSeverity(entries).map((e, i) => (
            <li key={i} className="px-5 py-3 border-t border-slate-100 first:border-t-0">
              {renderEntry(e)}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function DiffRow({ primary, muted }: { primary: Finding; muted: boolean }) {
  return (
    <div className="flex items-start gap-3">
      <span
        className={`shrink-0 inline-flex items-center px-2 py-0.5 rounded ring-1 ring-inset text-[10px] font-bold uppercase tracking-wider h-fit mt-0.5 ${SEV_BADGE[primary.severity]} ${muted ? 'opacity-60' : ''}`}
      >
        {primary.severity}
      </span>
      <div className="flex-1 min-w-0">
        {primary.target_name && (
          <p className={`text-[11px] font-mono ${muted ? 'text-slate-400' : 'text-slate-500'} mb-0.5`}>
            {primary.target_name}
          </p>
        )}
        <p className={`text-sm leading-relaxed ${muted ? 'text-slate-500' : 'text-slate-900'}`}>
          {primary.message}
        </p>
        <p className="text-[10px] font-mono text-slate-400 mt-1">{primary.rule_id}</p>
      </div>
    </div>
  )
}

function DiffRowChanged({ before, after }: { before: Finding; after: Finding }) {
  return (
    <div className="flex items-start gap-3">
      <span className="shrink-0 inline-flex items-center gap-1 mt-0.5">
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded ring-1 ring-inset text-[10px] font-bold uppercase tracking-wider ${SEV_BADGE[before.severity]} opacity-70 line-through decoration-slate-400/60`}
        >
          {before.severity}
        </span>
        <span className="text-slate-400 text-xs">→</span>
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded ring-1 ring-inset text-[10px] font-bold uppercase tracking-wider ${SEV_BADGE[after.severity]}`}
        >
          {after.severity}
        </span>
      </span>
      <div className="flex-1 min-w-0">
        {after.target_name && (
          <p className="text-[11px] font-mono text-slate-500 mb-0.5">
            {after.target_name}
          </p>
        )}
        <p className="text-sm text-slate-900 leading-relaxed">{after.message}</p>
        <p className="text-[10px] font-mono text-slate-400 mt-1">{after.rule_id}</p>
      </div>
    </div>
  )
}

// ── scan picker ──────────────────────────────────────────────

function ScanPicker({
  label,
  value,
  scans,
  latestId,
  onChange,
}: {
  label: string
  value: string
  scans: Scan[]
  latestId: string | undefined
  onChange: (id: string) => void
}) {
  return (
    <div>
      <label className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 block mb-1">
        {label}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-transparent"
      >
        {scans.map((s) => (
          <option key={s.id} value={s.id}>
            {fmtScanLabel(s)}{s.id === latestId ? ' · latest' : ''}
          </option>
        ))}
      </select>
    </div>
  )
}

// ── helpers ──────────────────────────────────────────────────

function computeDiff(a: ScanResult, b: ScanResult): DiffResult {
  const aMap = new Map<string, Finding>()
  for (const f of a.findings) aMap.set(findingKey(f), f)
  const bMap = new Map<string, Finding>()
  for (const f of b.findings) bMap.set(findingKey(f), f)

  const resolved: DiffEntry[] = []
  const added: DiffEntry[] = []
  const changed: DiffEntry[] = []
  const unchanged: DiffEntry[] = []

  for (const [key, fa] of aMap) {
    const fb = bMap.get(key)
    const base = {
      rule_id: fa.rule_id,
      dimension: fa.dimension,
      target_name: fa.target_name ?? `obj_${fa.target_obj_id}`,
    }
    if (!fb) {
      resolved.push({ ...base, before: fa })
    } else if (fa.severity !== fb.severity) {
      changed.push({ ...base, before: fa, after: fb })
    } else {
      unchanged.push({ ...base, before: fa, after: fb })
    }
  }
  for (const [key, fb] of bMap) {
    if (aMap.has(key)) continue
    added.push({
      rule_id: fb.rule_id,
      dimension: fb.dimension,
      target_name: fb.target_name ?? `obj_${fb.target_obj_id}`,
      after: fb,
    })
  }

  return { resolved, added, changed, unchanged }
}

function computeDimensionDeltas(
  a: ScanResult,
  b: ScanResult
): Array<{ dimension: Dimension; a: number; b: number; delta: number }> {
  const aByDim = new Map<Dimension, SubScore>()
  for (const s of a.sub_scores) aByDim.set(s.dimension, s)
  const out: Array<{ dimension: Dimension; a: number; b: number; delta: number }> = []
  for (const s of b.sub_scores) {
    const prev = aByDim.get(s.dimension)
    const aScore = prev?.score ?? s.score
    out.push({
      dimension: s.dimension,
      a: aScore,
      b: s.score,
      delta: s.score - aScore,
    })
  }
  return out
}

function findingKey(f: Finding): string {
  // target_obj_id is reassigned per scan and not stable; target_name is the
  // identity that survives across scans (entity / Entity.attribute).
  return `${f.rule_id}::${f.target_name ?? `obj_${f.target_obj_id}`}`
}

function sortByDimSeverity(entries: DiffEntry[]): DiffEntry[] {
  const sorted = [...entries]
  sorted.sort((x, y) => {
    if (x.dimension !== y.dimension) return x.dimension.localeCompare(y.dimension)
    const sxBefore = x.before?.severity
    const syBefore = y.before?.severity
    const sxAfter = x.after?.severity
    const syAfter = y.after?.severity
    const sx = sxBefore ?? sxAfter
    const sy = syBefore ?? syAfter
    if (sx && sy) return SEV_ORDER[sx] - SEV_ORDER[sy]
    return 0
  })
  return sorted
}

function fmtScanLabel(s: Scan): string {
  const d = new Date(s.scanned_at)
  const date = d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
  const grade = s.result.grade
  const composite = s.result.composite_score.toFixed(2)
  const findings = s.result.findings.length
  return `${date} · ${grade} (${composite}) · ${findings} finding${findings === 1 ? '' : 's'}`
}

function ArrowRight() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  )
}
