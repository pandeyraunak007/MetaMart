import { useState } from 'react'
import type { SavedModel } from '../types'
import { latestScan } from '../storage'
import ScoreHero from './ScoreHero'
import RadarPanel from './RadarPanel'
import SubScoreList from './SubScoreList'
import FindingsList from './FindingsList'

type Tab = 'overview' | 'score' | 'versions' | 'audit'

interface Props {
  model: SavedModel
  rescoring: boolean
  onRescore: () => void
  onRename: (name: string) => void
  onDelete: () => void
}

export default function ModelView({ model, rescoring, onRescore, onRename, onDelete }: Props) {
  const [tab, setTab] = useState<Tab>('score')
  const last = latestScan(model)

  return (
    <div className="flex flex-col h-full">
      <header className="border-b border-slate-200 bg-white px-8 pt-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
              Model
            </p>
            <h1 className="text-2xl font-semibold text-slate-900 truncate mt-0.5">
              {model.name}
            </h1>
            <p className="text-xs text-slate-500 mt-1">
              Created {fmtDate(model.created_at)}
              <span className="mx-2 text-slate-300">·</span>
              Updated {fmtDate(model.updated_at)}
              <span className="mx-2 text-slate-300">·</span>
              {model.scans.length} {model.scans.length === 1 ? 'scan' : 'scans'}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => {
                const name = prompt('Rename model:', model.name)
                if (name && name.trim()) onRename(name.trim())
              }}
              className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 hover:border-slate-300 hover:bg-slate-50"
            >
              Rename
            </button>
            <button
              onClick={onRescore}
              disabled={rescoring}
              className="rounded-md bg-amber-500 px-4 py-1.5 text-sm font-semibold text-white hover:bg-amber-600 disabled:opacity-50 transition-colors shadow-sm"
            >
              {rescoring ? 'Re-scoring…' : 'Re-score'}
            </button>
            <button
              onClick={() => {
                if (confirm(`Delete "${model.name}"? This can't be undone.`)) {
                  onDelete()
                }
              }}
              className="rounded-md border border-red-200 bg-white px-3 py-1.5 text-sm text-red-700 hover:border-red-300 hover:bg-red-50"
            >
              Delete
            </button>
          </div>
        </div>
        <nav className="mt-5 -mb-px flex gap-6">
          {(['overview', 'score', 'versions', 'audit'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`pb-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === t
                  ? 'border-amber-500 text-slate-900'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
              {t === 'versions' && (
                <span className="ml-1.5 text-[10px] font-mono text-slate-400">
                  {model.scans.length}
                </span>
              )}
            </button>
          ))}
        </nav>
      </header>

      <div className="flex-1 overflow-y-auto bg-slate-50 px-8 py-6">
        {tab === 'overview' && <OverviewTab model={model} />}
        {tab === 'score' && (
          last ? (
            <ScoreTab modelName={model.name} result={last.result} />
          ) : (
            <EmptyMsg text="No score yet. Click Re-score above." />
          )
        )}
        {tab === 'versions' && <VersionsTab model={model} />}
        {tab === 'audit' && <AuditTab model={model} />}
      </div>
    </div>
  )
}

// ── tabs ─────────────────────────────────────────────────────

function OverviewTab({ model }: { model: SavedModel }) {
  const stats = catalogStats(model.catalog_json)
  const preview = JSON.stringify(model.catalog_json, null, 2)
  const truncated = preview.length > 4000
  const previewText = truncated ? preview.slice(0, 4000) + '\n… (truncated)' : preview

  return (
    <div className="max-w-4xl space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <Stat label="Format" value={stats.format} />
        <Stat label="Top-level entities (raw)" value={stats.entitiesRaw} />
        <Stat label="JSON size" value={`${(preview.length / 1024).toFixed(1)} KB`} />
      </div>
      <div className="rounded-2xl bg-white border border-slate-200 p-6 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Source JSON</h3>
        <pre className="text-xs font-mono leading-relaxed text-slate-700 bg-slate-50 rounded-md border border-slate-200 p-4 overflow-x-auto max-h-[60vh]">
          {previewText}
        </pre>
      </div>
    </div>
  )
}

function ScoreTab({ modelName, result }: { modelName: string; result: import('../types').ScanResult }) {
  return (
    <div className="space-y-6">
      <ScoreHero result={result} modelName={modelName} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RadarPanel subScores={result.sub_scores} />
        <SubScoreList subScores={result.sub_scores} />
      </div>
      <FindingsList findings={result.findings} />
    </div>
  )
}

function VersionsTab({ model }: { model: SavedModel }) {
  if (model.scans.length === 0) {
    return <EmptyMsg text="No scans yet." />
  }
  // Build delta vs the next-older scan (scans are stored newest-first).
  return (
    <div className="rounded-2xl bg-white border border-slate-200 shadow-sm overflow-hidden max-w-4xl">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 border-b border-slate-200">
          <tr className="text-left text-xs uppercase tracking-wider text-slate-500">
            <th className="px-5 py-3 font-semibold">When</th>
            <th className="px-5 py-3 font-semibold">Grade</th>
            <th className="px-5 py-3 font-semibold">Composite</th>
            <th className="px-5 py-3 font-semibold">Δ</th>
            <th className="px-5 py-3 font-semibold">Findings</th>
          </tr>
        </thead>
        <tbody>
          {model.scans.map((scan, i) => {
            const prev = model.scans[i + 1]
            const delta = prev
              ? scan.result.composite_score - prev.result.composite_score
              : null
            return (
              <tr key={scan.id} className="border-b border-slate-100 last:border-b-0">
                <td className="px-5 py-3 text-slate-600">{fmtDate(scan.scanned_at)}</td>
                <td className="px-5 py-3 font-bold">{scan.result.grade}</td>
                <td className="px-5 py-3 font-mono tabular-nums">
                  {scan.result.composite_score.toFixed(2)}
                </td>
                <td className="px-5 py-3 font-mono text-xs">
                  {delta === null ? (
                    <span className="text-slate-400">—</span>
                  ) : delta > 0 ? (
                    <span className="text-emerald-600">+{delta.toFixed(2)}</span>
                  ) : delta < 0 ? (
                    <span className="text-red-600">{delta.toFixed(2)}</span>
                  ) : (
                    <span className="text-slate-400">0.00</span>
                  )}
                </td>
                <td className="px-5 py-3 text-slate-600">{scan.result.findings.length}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function AuditTab({ model }: { model: SavedModel }) {
  if (model.audit.length === 0) {
    return <EmptyMsg text="No audit events yet." />
  }
  return (
    <ol className="max-w-3xl space-y-3">
      {model.audit.map((evt) => (
        <li
          key={evt.id}
          className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm"
        >
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-xs uppercase tracking-wider font-semibold text-slate-500">
              {evt.kind.replace(/_/g, ' ')}
            </span>
            <span className="text-xs text-slate-400 font-mono">
              {fmtDate(evt.at)}
            </span>
          </div>
          <p className="text-sm text-slate-800 mt-1">{evt.message}</p>
        </li>
      ))}
    </ol>
  )
}

// ── tiny helpers ─────────────────────────────────────────────

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl bg-white border border-slate-200 p-4 shadow-sm">
      <p className="text-xs uppercase tracking-wider text-slate-500 font-semibold">
        {label}
      </p>
      <p className="text-2xl font-semibold text-slate-900 mt-1 tabular-nums">{value}</p>
    </div>
  )
}

function EmptyMsg({ text }: { text: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-200 bg-white/40 p-10 text-center max-w-2xl">
      <p className="text-sm text-slate-500">{text}</p>
    </div>
  )
}

function fmtDate(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function catalogStats(catalog: unknown): { format: string; entitiesRaw: string } {
  if (Array.isArray(catalog)) {
    const first = catalog[0]
    if (
      first &&
      typeof first === 'object' &&
      'Description' in first &&
      typeof (first as { Description?: string }).Description === 'string' &&
      (first as { Description: string }).Description.toLowerCase().includes('erwin')
    ) {
      return { format: 'erwin native (flat array)', entitiesRaw: `${catalog.length - 1} typed objects` }
    }
    return { format: 'list', entitiesRaw: `${catalog.length} items` }
  }
  if (catalog && typeof catalog === 'object') {
    const obj = catalog as Record<string, unknown>
    if (Array.isArray(obj.entities)) {
      return { format: 'native catalog', entitiesRaw: `${obj.entities.length} entities` }
    }
    if (Array.isArray(obj.tables)) {
      return { format: 'tables/columns', entitiesRaw: `${obj.tables.length} tables` }
    }
    if (obj.nodes && typeof obj.nodes === 'object') {
      return {
        format: 'dbt manifest',
        entitiesRaw: `${Object.keys(obj.nodes as object).length} nodes`,
      }
    }
    return { format: 'object', entitiesRaw: `${Object.keys(obj).length} top-level keys` }
  }
  return { format: typeof catalog, entitiesRaw: '–' }
}
