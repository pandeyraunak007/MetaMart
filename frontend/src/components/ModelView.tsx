import { useState } from 'react'
import type { SavedModel } from '../types'
import { latestScan } from '../storage'
import ScoreHero from './ScoreHero'
import RadarPanel from './RadarPanel'
import SubScoreList from './SubScoreList'
import FindingsList from './FindingsList'
import Sparkline from './Sparkline'

type Tab = 'overview' | 'score' | 'versions' | 'audit'

interface Props {
  model: SavedModel
  rescoring: boolean
  fixing: boolean
  fixingTarget: { ruleId: string; targetObjId: number } | null
  // The latest fix the user applied (Fix or Fix-all). Drives the post-fix
  // banner above the findings list with a prominent Download button.
  lastFix: { count: number; description: string } | null
  onDismissLastFix: () => void
  onRescore: () => void
  onRename: (name: string) => void
  onDelete: () => void
  onFix: (ruleId: string, targetObjId: number) => Promise<void> | void
  onFixAll: () => Promise<void> | void
  onFork: (newName: string) => void
}

export default function ModelView({
  model,
  rescoring,
  fixing,
  fixingTarget,
  lastFix,
  onDismissLastFix,
  onRescore,
  onRename,
  onDelete,
  onFix,
  onFixAll,
  onFork,
}: Props) {
  const [tab, setTab] = useState<Tab>('score')
  const last = latestScan(model)
  const fixCount = countFixes(model)

  function handleDownload() {
    const json = JSON.stringify(model.catalog_json, null, 2)
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const safeName = model.name.replace(/[^a-z0-9._-]+/gi, '_')
    a.download = `${safeName}.json`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    // Once they've downloaded, they've acted on the post-fix banner — drop it
    // so it doesn't keep nagging through subsequent unrelated edits.
    onDismissLastFix()
  }

  function handleFork() {
    const suggested = `${model.name} (copy)`
    const name = prompt('Save as a copy — name?', suggested)
    if (name && name.trim()) onFork(name.trim())
  }

  return (
    <div className="flex flex-col h-full">
      <header className="border-b border-slate-200 bg-white px-8 pt-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
              Model
            </p>
            <h1 className="text-2xl font-semibold text-slate-900 truncate mt-0.5 flex items-center gap-2.5">
              <span className="truncate">{model.name}</span>
              {fixCount > 0 && (
                <span
                  title={`This model has been auto-fixed ${fixCount} time${fixCount === 1 ? '' : 's'}. Use "Save as copy" to keep the original.`}
                  className="shrink-0 inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 ring-1 ring-emerald-200"
                >
                  <span className="text-emerald-500">●</span>
                  +{fixCount} fix{fixCount === 1 ? '' : 'es'}
                </span>
              )}
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
              onClick={handleDownload}
              title="Download the current saved JSON. Includes any auto-fixes you've applied."
              className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 hover:border-slate-300 hover:bg-slate-50 inline-flex items-center gap-1.5"
            >
              <DownloadIcon />
              Download <span className="text-slate-400 font-normal">(latest)</span>
            </button>
            <button
              onClick={handleFork}
              title="Save the current state as a new model"
              className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 hover:border-slate-300 hover:bg-slate-50"
            >
              Save as copy
            </button>
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
            <ScoreTab
              modelName={model.name}
              result={last.result}
              onFix={onFix}
              onFixAll={onFixAll}
              fixing={fixing}
              fixingTarget={fixingTarget}
              lastFix={lastFix}
              onDownload={handleDownload}
              onDismissLastFix={onDismissLastFix}
              onOpenAudit={() => setTab('audit')}
            />
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

function ScoreTab({
  modelName,
  result,
  onFix,
  onFixAll,
  fixing,
  fixingTarget,
  lastFix,
  onDownload,
  onDismissLastFix,
  onOpenAudit,
}: {
  modelName: string
  result: import('../types').ScanResult
  onFix: (ruleId: string, targetObjId: number) => Promise<void> | void
  onFixAll: () => Promise<void> | void
  fixing: boolean
  fixingTarget: { ruleId: string; targetObjId: number } | null
  lastFix: { count: number; description: string } | null
  onDownload: () => void
  onDismissLastFix: () => void
  onOpenAudit: () => void
}) {
  return (
    <div className="space-y-6">
      <ScoreHero result={result} modelName={modelName} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RadarPanel subScores={result.sub_scores} />
        <SubScoreList subScores={result.sub_scores} />
      </div>
      {lastFix && (
        <PostFixBanner
          fix={lastFix}
          grade={result.grade}
          composite={result.composite_score}
          onDownload={onDownload}
          onDismiss={onDismissLastFix}
          onOpenAudit={onOpenAudit}
        />
      )}
      <FindingsList
        findings={result.findings}
        onFix={onFix}
        onFixAll={onFixAll}
        fixing={fixing}
        fixingTarget={fixingTarget}
      />
    </div>
  )
}

function PostFixBanner({
  fix,
  grade,
  composite,
  onDownload,
  onDismiss,
  onOpenAudit,
}: {
  fix: { count: number; description: string }
  grade: string
  composite: number
  onDownload: () => void
  onDismiss: () => void
  onOpenAudit: () => void
}) {
  const headline =
    fix.count > 1
      ? `Applied ${fix.count} fixes. Score is now ${grade} (${composite.toFixed(2)}).`
      : `Fix applied. Score is now ${grade} (${composite.toFixed(2)}).`
  return (
    <div
      role="status"
      className="rounded-2xl border-2 border-emerald-200 bg-emerald-50 p-5 shadow-sm flex items-start gap-4"
    >
      <div className="shrink-0 mt-0.5 h-9 w-9 rounded-full bg-emerald-500 flex items-center justify-center text-white">
        <CheckIcon />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-emerald-900">{headline}</p>
        {fix.count === 1 && (
          <p className="text-xs text-emerald-800 mt-0.5 truncate">{fix.description}</p>
        )}
        <p className="text-xs text-emerald-700/80 mt-2">
          Your saved model now reflects these changes. Download the JSON to use
          it (the file stays in its original format).
        </p>
        <div className="mt-3 flex items-center gap-2">
          <button
            onClick={onDownload}
            className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 transition-colors shadow-sm inline-flex items-center gap-1.5"
          >
            <DownloadIcon />
            Download fixed JSON
          </button>
          <button
            onClick={onOpenAudit}
            className="rounded-md border border-emerald-300 bg-white px-3 py-1.5 text-xs font-semibold text-emerald-800 hover:bg-emerald-50 transition-colors"
          >
            View change log
          </button>
        </div>
      </div>
      <button
        onClick={onDismiss}
        title="Dismiss"
        className="shrink-0 -mt-1 -mr-1 p-1 text-emerald-700/60 hover:text-emerald-900"
      >
        <CloseIcon />
      </button>
    </div>
  )
}

function countFixes(model: SavedModel): number {
  return model.audit.filter((e) => /^Fix(?:-all)?:/i.test(e.message)).length
}

function DownloadIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

function VersionsTab({ model }: { model: SavedModel }) {
  if (model.scans.length === 0) {
    return <EmptyMsg text="No scans yet." />
  }
  const series = model.scans.map((s) => s.result.composite_score)  // newest-first
  const latest = series[0]
  const oldest = series[series.length - 1]
  const trend = series.length > 1 ? latest - oldest : 0
  const min = Math.min(...series)
  const max = Math.max(...series)

  return (
    <div className="max-w-4xl space-y-6">
      <div className="rounded-2xl bg-white border border-slate-200 p-6 shadow-sm">
        <div className="flex items-center justify-between gap-6">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
              Score trend
            </p>
            <p className="text-3xl font-semibold text-slate-900 tabular-nums mt-1">
              {latest.toFixed(2)}
              {series.length > 1 && (
                <span
                  className={`ml-3 text-sm font-mono ${
                    trend > 0
                      ? 'text-emerald-600'
                      : trend < 0
                        ? 'text-red-600'
                        : 'text-slate-400'
                  }`}
                >
                  {trend > 0 ? '+' : ''}
                  {trend.toFixed(2)} since first
                </span>
              )}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              {series.length} {series.length === 1 ? 'scan' : 'scans'}
              <span className="mx-1.5 text-slate-300">·</span>
              min {min.toFixed(2)}
              <span className="mx-1.5 text-slate-300">·</span>
              max {max.toFixed(2)}
            </p>
          </div>
          <Sparkline values={series} width={240} height={64} />
        </div>
      </div>

      <div className="rounded-2xl bg-white border border-slate-200 shadow-sm overflow-hidden">
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
