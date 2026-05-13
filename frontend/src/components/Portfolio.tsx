import { useMemo, useState, type ReactNode } from 'react'
import type { MartState, Severity } from '../types'
import { latestScan } from '../storage'
import Sparkline from './Sparkline'

interface Props {
  state: MartState
  onOpenModel: (modelId: string, folderId: string, libraryId: string) => void
}

interface Row {
  modelId: string
  folderId: string
  libraryId: string
  name: string
  path: string                       // "Library / Folder"
  grade: string
  composite: number | null
  history: number[]                  // newest-first composite scores
  findingCount: number
  severityCounts: Record<Severity, number>
  lastScannedAt: string | null
  createdAt: string
}

type SortKey = 'name' | 'path' | 'composite' | 'findings' | 'lastScannedAt'
type SortDir = 'asc' | 'desc'

const GRADE_TEXT: Record<string, string> = {
  A: 'text-emerald-700 bg-emerald-50 ring-emerald-200',
  B: 'text-lime-700 bg-lime-50 ring-lime-200',
  C: 'text-amber-700 bg-amber-50 ring-amber-200',
  D: 'text-orange-700 bg-orange-50 ring-orange-200',
  F: 'text-red-700 bg-red-50 ring-red-200',
}

const SEV_DOT: Record<Severity, string> = {
  critical: 'bg-red-500',
  error: 'bg-orange-500',
  warn: 'bg-amber-400',
  info: 'bg-slate-300',
}

export default function Portfolio({ state, onOpenModel }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('composite')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  const rows = useMemo<Row[]>(() => {
    const out: Row[] = []
    for (const lib of state.libraries) {
      for (const fld of lib.folders) {
        for (const m of fld.models) {
          const last = latestScan(m)
          const sev: Record<Severity, number> = {
            critical: 0,
            error: 0,
            warn: 0,
            info: 0,
          }
          if (last) {
            for (const f of last.result.findings) sev[f.severity]++
          }
          out.push({
            modelId: m.id,
            folderId: fld.id,
            libraryId: lib.id,
            name: m.name,
            path: `${lib.name} / ${fld.name}`,
            grade: last?.result.grade ?? '–',
            composite: last?.result.composite_score ?? null,
            history: m.scans.map((s) => s.result.composite_score),
            findingCount: last?.result.findings.length ?? 0,
            severityCounts: sev,
            lastScannedAt: last?.scanned_at ?? null,
            createdAt: m.created_at,
          })
        }
      }
    }
    return sortRows(out, sortKey, sortDir)
  }, [state, sortKey, sortDir])

  const totals = useMemo(() => {
    const scored = rows.filter((r) => r.composite !== null)
    const avg =
      scored.length > 0
        ? scored.reduce((acc, r) => acc + (r.composite ?? 0), 0) / scored.length
        : null
    const gradeBreakdown: Record<string, number> = { A: 0, B: 0, C: 0, D: 0, F: 0 }
    for (const r of rows) {
      if (r.grade in gradeBreakdown) gradeBreakdown[r.grade]++
    }
    return { count: rows.length, avg, gradeBreakdown }
  }, [rows])

  function toggleSort(k: SortKey) {
    if (sortKey === k) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(k)
      setSortDir(k === 'name' || k === 'path' ? 'asc' : 'asc')
    }
  }

  if (rows.length === 0) {
    return (
      <div className="h-full flex items-center justify-center px-8">
        <div className="rounded-2xl border border-dashed border-slate-200 bg-white/40 p-12 text-center max-w-lg">
          <p className="text-base text-slate-700 font-medium">No models yet</p>
          <p className="text-sm text-slate-500 mt-2">
            Switch back to <span className="font-medium">Browse</span>, pick a folder, and upload a JSON to get started.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <header className="border-b border-slate-200 bg-white px-8 py-6">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
          Portfolio
        </p>
        <h1 className="text-2xl font-semibold text-slate-900 mt-0.5">
          {totals.count} {totals.count === 1 ? 'model' : 'models'} across all libraries
        </h1>
        <div className="mt-4 flex flex-wrap gap-3">
          <Stat label="Average score" value={totals.avg !== null ? totals.avg.toFixed(1) : '–'} />
          {(['A', 'B', 'C', 'D', 'F'] as const).map((g) => (
            <GradeStat key={g} grade={g} count={totals.gradeBreakdown[g]} />
          ))}
        </div>
      </header>

      <div className="flex-1 overflow-auto bg-slate-50 px-8 py-6">
        <div className="rounded-2xl bg-white border border-slate-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr className="text-left text-xs uppercase tracking-wider text-slate-500">
                <SortHeader k="name" current={sortKey} dir={sortDir} onSort={toggleSort}>Model</SortHeader>
                <SortHeader k="path" current={sortKey} dir={sortDir} onSort={toggleSort}>Folder</SortHeader>
                <th className="px-4 py-3 font-semibold">Grade</th>
                <SortHeader k="composite" current={sortKey} dir={sortDir} onSort={toggleSort}>Composite</SortHeader>
                <th className="px-4 py-3 font-semibold">Trend</th>
                <SortHeader k="findings" current={sortKey} dir={sortDir} onSort={toggleSort}>Findings</SortHeader>
                <SortHeader k="lastScannedAt" current={sortKey} dir={sortDir} onSort={toggleSort}>Last scanned</SortHeader>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.modelId}
                  onClick={() => onOpenModel(r.modelId, r.folderId, r.libraryId)}
                  className="border-b border-slate-100 last:border-b-0 cursor-pointer hover:bg-amber-50/40"
                >
                  <td className="px-4 py-3 font-medium text-slate-900 truncate max-w-[18rem]">{r.name}</td>
                  <td className="px-4 py-3 text-slate-600 text-xs">{r.path}</td>
                  <td className="px-4 py-3">
                    <GradeBadge grade={r.grade} />
                  </td>
                  <td className="px-4 py-3 font-mono tabular-nums text-slate-800">
                    {r.composite !== null ? r.composite.toFixed(2) : '–'}
                  </td>
                  <td className="px-4 py-3">
                    <Sparkline
                      values={r.history}
                      title={`${r.history.length} scan${r.history.length === 1 ? '' : 's'}`}
                    />
                  </td>
                  <td className="px-4 py-3">
                    <FindingsCell count={r.findingCount} sev={r.severityCounts} />
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600 whitespace-nowrap">
                    {r.lastScannedAt ? fmtRelative(r.lastScannedAt) : '–'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ── helpers ──────────────────────────────────────────────────

function sortRows(rows: Row[], key: SortKey, dir: SortDir): Row[] {
  const mul = dir === 'asc' ? 1 : -1
  const sorted = [...rows]
  sorted.sort((a, b) => {
    const av = pick(a, key)
    const bv = pick(b, key)
    if (av === null && bv === null) return 0
    if (av === null) return 1
    if (bv === null) return -1
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * mul
    return String(av).localeCompare(String(bv)) * mul
  })
  return sorted
}

function pick(r: Row, k: SortKey): string | number | null {
  switch (k) {
    case 'name': return r.name
    case 'path': return r.path
    case 'composite': return r.composite
    case 'findings': return r.findingCount
    case 'lastScannedAt': return r.lastScannedAt
  }
}

function GradeBadge({ grade }: { grade: string }) {
  const style = GRADE_TEXT[grade] ?? 'text-slate-500 bg-slate-50 ring-slate-200'
  return (
    <span className={`inline-flex items-center justify-center min-w-[1.6rem] px-1.5 py-0.5 rounded text-xs font-bold ring-1 ring-inset ${style}`}>
      {grade}
    </span>
  )
}

function FindingsCell({ count, sev }: { count: number; sev: Record<Severity, number> }) {
  if (count === 0) {
    return <span className="text-slate-400 text-xs">clean</span>
  }
  return (
    <div className="flex items-center gap-2">
      <span className="font-mono tabular-nums text-slate-800">{count}</span>
      <span className="flex items-center gap-1">
        {(['critical', 'error', 'warn', 'info'] as const).map((s) =>
          sev[s] > 0 ? (
            <span key={s} title={`${sev[s]} ${s}`} className="flex items-center gap-0.5">
              <span className={`h-1.5 w-1.5 rounded-full ${SEV_DOT[s]}`} />
              <span className="text-[10px] font-mono text-slate-500">{sev[s]}</span>
            </span>
          ) : null
        )}
      </span>
    </div>
  )
}

function SortHeader({
  k,
  current,
  dir,
  onSort,
  children,
}: {
  k: SortKey
  current: SortKey
  dir: SortDir
  onSort: (k: SortKey) => void
  children: ReactNode
}) {
  const active = k === current
  return (
    <th className="px-4 py-3 font-semibold">
      <button
        onClick={() => onSort(k)}
        className={`inline-flex items-center gap-1 hover:text-slate-800 transition-colors ${active ? 'text-slate-900' : ''}`}
      >
        {children}
        {active && <span className="text-[9px]">{dir === 'asc' ? '▲' : '▼'}</span>}
      </button>
    </th>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-2">
      <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
        {label}
      </p>
      <p className="text-lg font-semibold text-slate-900 tabular-nums">{value}</p>
    </div>
  )
}

function GradeStat({ grade, count }: { grade: string; count: number }) {
  const style = GRADE_TEXT[grade] ?? ''
  return (
    <div className={`rounded-lg border px-3 py-2 flex items-center gap-2 ${count > 0 ? `bg-white border-slate-200` : 'bg-slate-50 border-slate-100 opacity-60'}`}>
      <span className={`inline-flex items-center justify-center min-w-[1.4rem] px-1 rounded text-[10px] font-bold ring-1 ring-inset ${style}`}>{grade}</span>
      <span className="text-sm font-mono tabular-nums text-slate-700">{count}</span>
    </div>
  )
}

function fmtRelative(iso: string): string {
  const then = new Date(iso).getTime()
  const now = Date.now()
  const diffSec = Math.round((now - then) / 1000)
  if (diffSec < 60) return `${diffSec}s ago`
  if (diffSec < 3600) return `${Math.round(diffSec / 60)}m ago`
  if (diffSec < 86400) return `${Math.round(diffSec / 3600)}h ago`
  if (diffSec < 86400 * 7) return `${Math.round(diffSec / 86400)}d ago`
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

