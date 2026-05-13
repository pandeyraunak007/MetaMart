import type { ScanResult } from '../types'

const GRADE_STYLES: Record<string, { bg: string; ring: string; label: string }> = {
  A: { bg: 'bg-emerald-500', ring: 'ring-emerald-200', label: 'Excellent' },
  B: { bg: 'bg-lime-500', ring: 'ring-lime-200', label: 'Good' },
  C: { bg: 'bg-amber-500', ring: 'ring-amber-200', label: 'Fair' },
  D: { bg: 'bg-orange-500', ring: 'ring-orange-200', label: 'Poor' },
  F: { bg: 'bg-red-500', ring: 'ring-red-200', label: 'Failing' },
}

interface Props {
  result: ScanResult
  modelName: string
}

export default function ScoreHero({ result, modelName }: Props) {
  const style = GRADE_STYLES[result.grade] ?? GRADE_STYLES.F

  return (
    <div className="rounded-2xl bg-white border border-slate-200 p-8 flex items-center gap-8 shadow-sm">
      <div
        className={`${style.bg} ring-8 ${style.ring} flex h-32 w-32 shrink-0 items-center justify-center rounded-3xl text-white shadow-lg`}
      >
        <span className="text-7xl font-bold leading-none tracking-tight">
          {result.grade}
        </span>
      </div>
      <div className="flex-1 min-w-0">
        {modelName && (
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest truncate">
            {modelName}
          </p>
        )}
        <p className="mt-1.5 text-6xl font-bold tabular-nums text-slate-900">
          {result.composite_score.toFixed(1)}
          <span className="text-2xl font-normal text-slate-400 ml-2">/ 100</span>
        </p>
        <p className="mt-3 text-sm text-slate-600">
          <span className="font-medium text-slate-900">{style.label}</span>
          <span className="mx-2 text-slate-300">·</span>
          {result.findings.length} {result.findings.length === 1 ? 'finding' : 'findings'} across 7 dimensions
          <span className="mx-2 text-slate-300">·</span>
          rule pack <span className="font-mono text-slate-700">{result.pack_id}</span>
        </p>
      </div>
    </div>
  )
}
