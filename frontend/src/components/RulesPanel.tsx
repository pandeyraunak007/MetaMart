import { useEffect, useMemo, useState } from 'react'
import type {
  Dimension,
  MartState,
  PackOverrides,
  RuleOverride,
  RuleSpecRead,
  ScanResult,
  Severity,
  SubScore,
} from '../types'
import { listRules, scoreJson } from '../api'
import { RULE_INFO } from '../ruleInfo'

interface Props {
  state: MartState
  onSave: (pack: PackOverrides | null) => void
}

const SEVERITY_OPTIONS: Severity[] = ['info', 'warn', 'error', 'critical']

const SEV_TONE: Record<Severity, string> = {
  info: 'bg-slate-100 text-slate-700 ring-slate-200',
  warn: 'bg-amber-100 text-amber-800 ring-amber-200',
  error: 'bg-orange-100 text-orange-800 ring-orange-200',
  critical: 'bg-red-100 text-red-800 ring-red-200',
}

export default function RulesPanel({ state, onSave }: Props) {
  const [rules, setRules] = useState<RuleSpecRead[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  // Working draft — lets the user mutate locally before clicking Save.
  // Initialized from the persisted custom_pack on mount; resets when the
  // saved pack changes from outside (e.g. user clicks Reset).
  const [draft, setDraft] = useState<Map<string, RuleOverride>>(
    () => packToMap(state.custom_pack ?? null)
  )

  useEffect(() => {
    setDraft(packToMap(state.custom_pack ?? null))
  }, [state.custom_pack])

  useEffect(() => {
    listRules()
      .then(setRules)
      .catch((e) => setLoadError(e instanceof Error ? e.message : String(e)))
  }, [])

  const dirty = useMemo(
    () => !sameOverrides(state.custom_pack ?? null, mapToPack(draft)),
    [state.custom_pack, draft]
  )

  if (loadError) {
    return (
      <div className="h-full flex items-center justify-center px-8">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 max-w-lg">
          <p className="text-sm font-semibold text-red-900">Couldn't load rules</p>
          <p className="text-xs text-red-800 mt-1 font-mono">{loadError}</p>
        </div>
      </div>
    )
  }

  if (!rules) {
    return (
      <div className="h-full flex items-center justify-center text-sm text-slate-400">
        Loading rules…
      </div>
    )
  }

  // Group rules by dimension for the layout.
  const byDim = new Map<Dimension, RuleSpecRead[]>()
  for (const r of rules) {
    if (!byDim.has(r.dimension)) byDim.set(r.dimension, [])
    byDim.get(r.dimension)!.push(r)
  }

  function setOverride(ruleId: string, patch: Partial<RuleOverride>) {
    setDraft((prev) => {
      const next = new Map(prev)
      const existing = next.get(ruleId) ?? { rule_id: ruleId }
      const merged: RuleOverride = { ...existing, ...patch, rule_id: ruleId }
      // Strip back to nothing-overridden so the saved pack stays minimal.
      const isNoop =
        (merged.enabled === undefined || merged.enabled === true) &&
        merged.severity_override === undefined &&
        (!merged.params_override || Object.keys(merged.params_override).length === 0)
      if (isNoop) next.delete(ruleId)
      else next.set(ruleId, merged)
      return next
    })
  }

  function reset() {
    setDraft(new Map())
  }

  function save() {
    onSave(mapToPack(draft))
  }

  const activeOverrides = state.custom_pack?.rules.length ?? 0

  return (
    <div className="h-full flex flex-col">
      <header className="border-b border-slate-200 bg-white px-8 py-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
              Rule pack
            </p>
            <h1 className="text-2xl font-semibold text-slate-900 mt-0.5">
              Configure scoring
            </h1>
            <p className="text-sm text-slate-500 mt-1 max-w-2xl">
              Disable rules that don't apply to your domain, or raise / lower
              severity. Saved settings apply to every score, fix, and re-score
              call until you reset.
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={reset}
              disabled={draft.size === 0 && activeOverrides === 0}
              className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 hover:border-slate-300 hover:bg-slate-50 disabled:opacity-40"
            >
              Reset to defaults
            </button>
            <button
              onClick={save}
              disabled={!dirty}
              className="rounded-md bg-amber-500 px-4 py-1.5 text-sm font-semibold text-white hover:bg-amber-600 disabled:opacity-50 transition-colors shadow-sm"
            >
              {dirty ? 'Save pack' : 'Saved'}
            </button>
          </div>
        </div>
        <div className="mt-4 flex items-center gap-3 text-xs">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full pl-2 pr-2.5 py-0.5 ring-1 ${
              activeOverrides === 0
                ? 'bg-slate-100 text-slate-600 ring-slate-200'
                : 'bg-amber-100 text-amber-900 ring-amber-200 font-semibold'
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                activeOverrides === 0 ? 'bg-slate-400' : 'bg-amber-500'
              }`}
            />
            {activeOverrides === 0
              ? 'Default pack active'
              : `Custom pack active (${activeOverrides} override${activeOverrides === 1 ? '' : 's'})`}
          </span>
          {dirty && (
            <span className="text-slate-500 italic">
              Unsaved changes — click Save pack to apply.
            </span>
          )}
        </div>
      </header>

      <div className="flex-1 overflow-y-auto bg-slate-50 px-8 py-6">
        <div className="max-w-4xl space-y-5">
          <ImpactPreview state={state} draftPack={mapToPack(draft)} />
          {[...byDim.entries()].map(([dim, rs]) => (
            <DimensionSection
              key={dim}
              dimension={dim}
              rules={rs}
              draft={draft}
              setOverride={setOverride}
              dirtyDelta={countOverridesInDim(draft, rs)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

// ── per-dimension card ───────────────────────────────────────

function DimensionSection({
  dimension,
  rules,
  draft,
  setOverride,
  dirtyDelta,
}: {
  dimension: Dimension
  rules: RuleSpecRead[]
  draft: Map<string, RuleOverride>
  setOverride: (ruleId: string, patch: Partial<RuleOverride>) => void
  dirtyDelta: number
}) {
  return (
    <section className="rounded-2xl bg-white border border-slate-200 shadow-sm overflow-hidden">
      <header className="px-5 py-3 border-b border-slate-200 bg-slate-50 flex items-baseline justify-between">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">
          {dimension}
        </h2>
        <span className="text-xs text-slate-500">
          {rules.length} rule{rules.length === 1 ? '' : 's'}
          {dirtyDelta > 0 && (
            <>
              <span className="mx-1.5 text-slate-300">·</span>
              <span className="text-amber-700 font-medium">
                {dirtyDelta} customized
              </span>
            </>
          )}
        </span>
      </header>
      <ul className="divide-y divide-slate-100">
        {rules.map((r) => (
          <RuleRow
            key={r.rule_id}
            rule={r}
            override={draft.get(r.rule_id)}
            setOverride={setOverride}
          />
        ))}
      </ul>
    </section>
  )
}

function RuleRow({
  rule,
  override,
  setOverride,
}: {
  rule: RuleSpecRead
  override: RuleOverride | undefined
  setOverride: (ruleId: string, patch: Partial<RuleOverride>) => void
}) {
  const enabled = override?.enabled !== false
  const severity = override?.severity_override ?? rule.default_severity
  const info = RULE_INFO[rule.rule_id]

  // Most-tunable param: max_length (only one we expose in v1; future-proof
  // by keeping the editor extensible per rule_id).
  const maxLengthParam =
    rule.rule_id === 'naming.max_length'
      ? Number(
          override?.params_override?.max_length ??
            rule.default_params.max_length ??
            64
        )
      : null

  return (
    <li className="px-5 py-4">
      <div className="flex items-start gap-4">
        <Toggle
          checked={enabled}
          onChange={(v) => setOverride(rule.rule_id, { enabled: v })}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <code className="text-sm font-mono font-semibold text-slate-900">
              {rule.rule_id}
            </code>
            {rule.has_fixer && (
              <span
                title="Has an auto-fix"
                className="text-[10px] uppercase tracking-wider font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded ring-1 ring-emerald-200"
              >
                Auto-fix
              </span>
            )}
            {!enabled && (
              <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                Disabled
              </span>
            )}
          </div>
          {info?.summary && (
            <p className="text-xs text-slate-600 mt-1 leading-relaxed">
              {info.summary}
            </p>
          )}
          {maxLengthParam !== null && enabled && (
            <div className="mt-2 flex items-center gap-2">
              <label className="text-[11px] uppercase tracking-wider font-semibold text-slate-500">
                Max length
              </label>
              <input
                type="number"
                min={1}
                max={1024}
                value={maxLengthParam}
                onChange={(e) => {
                  const v = Number(e.target.value)
                  if (Number.isFinite(v) && v > 0) {
                    setOverride(rule.rule_id, {
                      params_override: { max_length: v },
                    })
                  }
                }}
                className="w-20 rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-transparent"
              />
              {maxLengthParam !== rule.default_params.max_length && (
                <button
                  onClick={() =>
                    setOverride(rule.rule_id, { params_override: {} })
                  }
                  className="text-[11px] text-slate-500 hover:text-slate-800"
                >
                  Reset to {String(rule.default_params.max_length)}
                </button>
              )}
            </div>
          )}
        </div>
        <div className="shrink-0">
          <SeverityPicker
            value={severity}
            defaultValue={rule.default_severity}
            disabled={!enabled}
            onChange={(s) =>
              setOverride(rule.rule_id, {
                severity_override: s === rule.default_severity ? undefined : s,
              })
            }
          />
        </div>
      </div>
    </li>
  )
}

// ── controls ─────────────────────────────────────────────────

function Toggle({
  checked,
  onChange,
}: {
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`mt-0.5 shrink-0 relative h-5 w-9 rounded-full transition-colors ${
        checked ? 'bg-emerald-500' : 'bg-slate-300'
      }`}
    >
      <span
        className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
          checked ? 'translate-x-4' : 'translate-x-0.5'
        }`}
      />
    </button>
  )
}

function SeverityPicker({
  value,
  defaultValue,
  disabled,
  onChange,
}: {
  value: Severity
  defaultValue: Severity
  disabled: boolean
  onChange: (s: Severity) => void
}) {
  const isOverride = value !== defaultValue
  return (
    <div className="flex items-center gap-2">
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded ring-1 ring-inset text-[10px] font-bold uppercase tracking-wider ${SEV_TONE[value]} ${disabled ? 'opacity-50' : ''}`}
      >
        {value}
      </span>
      <select
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value as Severity)}
        className={`rounded-md border bg-white px-2 py-1 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-transparent ${
          isOverride ? 'border-amber-300' : 'border-slate-200'
        } disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        {SEVERITY_OPTIONS.map((s) => (
          <option key={s} value={s}>
            {s}
            {s === defaultValue ? ' (default)' : ''}
          </option>
        ))}
      </select>
    </div>
  )
}

// ── impact preview ───────────────────────────────────────────

function ImpactPreview({
  state,
  draftPack,
}: {
  state: MartState
  draftPack: PackOverrides | null
}) {
  const candidates = useMemo(() => {
    const out: Array<{ id: string; label: string; catalog: unknown }> = []
    for (const lib of state.libraries) {
      for (const fld of lib.folders) {
        for (const m of fld.models) {
          out.push({
            id: m.id,
            label: `${lib.name} / ${fld.name} / ${m.name}`,
            catalog: m.catalog_json,
          })
        }
      }
    }
    return out
  }, [state])

  const [modelId, setModelId] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [preview, setPreview] = useState<{
    base: ScanResult
    custom: ScanResult
  } | null>(null)

  async function run() {
    const target = candidates.find((c) => c.id === modelId)
    if (!target) return
    setLoading(true)
    setErr(null)
    try {
      // Fire both scores in parallel; eMovies takes <1s on the live API.
      const [base, custom] = await Promise.all([
        scoreJson(target.catalog, null),
        scoreJson(target.catalog, draftPack),
      ])
      setPreview({ base, custom })
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
      setPreview(null)
    } finally {
      setLoading(false)
    }
  }

  if (candidates.length === 0) return null

  const compositeDelta = preview
    ? preview.custom.composite_score - preview.base.composite_score
    : null

  return (
    <section className="rounded-2xl bg-white border border-slate-200 shadow-sm p-5">
      <div className="flex items-baseline justify-between gap-3 mb-3">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">
            Impact preview
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Pick a saved model to see what your draft pack would do to it.
          </p>
        </div>
      </div>
      <div className="flex items-end gap-2 flex-wrap">
        <div className="flex-1 min-w-[16rem]">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 block mb-1">
            Model
          </label>
          <select
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
            className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-transparent"
          >
            <option value="">Choose a saved model…</option>
            {candidates.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={run}
          disabled={!modelId || loading}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50 transition-colors shadow-sm"
        >
          {loading ? 'Scoring…' : 'Run preview'}
        </button>
      </div>
      {err && (
        <p className="mt-3 text-xs text-red-700 font-mono">{err}</p>
      )}
      {preview && compositeDelta !== null && (
        <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-baseline gap-6 flex-wrap">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                Default pack
              </p>
              <p className="text-2xl font-bold tabular-nums text-slate-900 mt-0.5">
                {preview.base.composite_score.toFixed(2)}
                <span className="ml-2 text-sm text-slate-500">{preview.base.grade}</span>
              </p>
            </div>
            <div className="text-2xl text-slate-300">→</div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                Draft pack
              </p>
              <p className="text-2xl font-bold tabular-nums text-slate-900 mt-0.5">
                {preview.custom.composite_score.toFixed(2)}
                <span className="ml-2 text-sm text-slate-500">{preview.custom.grade}</span>
              </p>
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                Delta
              </p>
              <p
                className={`text-2xl font-bold tabular-nums mt-0.5 ${
                  compositeDelta > 0.01
                    ? 'text-emerald-700'
                    : compositeDelta < -0.01
                      ? 'text-red-700'
                      : 'text-slate-500'
                }`}
              >
                {compositeDelta > 0 ? '+' : ''}
                {compositeDelta.toFixed(2)}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                Findings
              </p>
              <p className="text-2xl font-bold tabular-nums text-slate-900 mt-0.5">
                {preview.base.findings.length}
                <span className="mx-1 text-slate-300">→</span>
                {preview.custom.findings.length}
              </p>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-200 flex flex-wrap gap-1.5">
            {dimensionDeltas(preview.base, preview.custom).map((d) => (
              <span
                key={d.dimension}
                title={`${d.dimension}: ${d.base.toFixed(2)} → ${d.custom.toFixed(2)}`}
                className={`inline-flex items-center gap-1.5 rounded-full pl-2.5 pr-2 py-0.5 text-xs ring-1 ${
                  d.delta > 0.01
                    ? 'bg-emerald-100 text-emerald-900 ring-emerald-200'
                    : d.delta < -0.01
                      ? 'bg-red-100 text-red-900 ring-red-200'
                      : 'bg-white text-slate-600 ring-slate-200'
                }`}
              >
                <span className="capitalize">{d.dimension}</span>
                <span className="font-mono font-semibold tabular-nums">
                  {Math.abs(d.delta) < 0.01 ? '0' : `${d.delta > 0 ? '+' : ''}${d.delta.toFixed(1)}`}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

// ── pack <-> map helpers ─────────────────────────────────────

function packToMap(pack: PackOverrides | null): Map<string, RuleOverride> {
  const m = new Map<string, RuleOverride>()
  if (pack) for (const r of pack.rules) m.set(r.rule_id, r)
  return m
}

function mapToPack(m: Map<string, RuleOverride>): PackOverrides | null {
  if (m.size === 0) return null
  return { rules: [...m.values()] }
}

function sameOverrides(a: PackOverrides | null, b: PackOverrides | null): boolean {
  const aJson = JSON.stringify(a?.rules ?? [])
  const bJson = JSON.stringify(b?.rules ?? [])
  return aJson === bJson
}

function countOverridesInDim(
  draft: Map<string, RuleOverride>,
  rules: RuleSpecRead[]
): number {
  let n = 0
  for (const r of rules) {
    if (draft.has(r.rule_id)) n++
  }
  return n
}

function dimensionDeltas(
  a: ScanResult,
  b: ScanResult
): Array<{ dimension: Dimension; base: number; custom: number; delta: number }> {
  const aBy = new Map<Dimension, SubScore>()
  for (const s of a.sub_scores) aBy.set(s.dimension, s)
  const out: Array<{ dimension: Dimension; base: number; custom: number; delta: number }> = []
  for (const s of b.sub_scores) {
    const base = aBy.get(s.dimension)?.score ?? s.score
    out.push({ dimension: s.dimension, base, custom: s.score, delta: s.score - base })
  }
  return out
}
