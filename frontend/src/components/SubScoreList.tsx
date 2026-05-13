import type { SubScore } from '../types'

interface Props {
  subScores: SubScore[]
}

function colorForScore(score: number): string {
  if (score >= 90) return 'bg-emerald-500'
  if (score >= 80) return 'bg-lime-500'
  if (score >= 70) return 'bg-amber-500'
  if (score >= 60) return 'bg-orange-500'
  return 'bg-red-500'
}

export default function SubScoreList({ subScores }: Props) {
  const sorted = [...subScores].sort((a, b) => a.score - b.score)

  return (
    <div className="rounded-2xl bg-white border border-slate-200 p-6 shadow-sm">
      <h3 className="text-sm font-semibold text-slate-700 mb-1">Worst → best</h3>
      <p className="text-xs text-slate-500 mb-4">Per-dimension breakdown</p>
      <ul className="space-y-4">
        {sorted.map((s) => {
          const nonZero = Object.entries(s.finding_count_by_severity).filter(
            ([, n]) => n > 0
          )
          return (
            <li key={s.dimension}>
              <div className="flex items-baseline justify-between mb-1.5">
                <span className="text-sm font-medium capitalize text-slate-900">
                  {s.dimension}
                </span>
                <span className="text-sm font-mono tabular-nums font-semibold text-slate-700">
                  {s.score.toFixed(1)}
                </span>
              </div>
              <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className={`h-full rounded-full ${colorForScore(s.score)} transition-all duration-500`}
                  style={{ width: `${s.score}%` }}
                />
              </div>
              <p className="text-xs text-slate-500 mt-1.5">
                <span>population {s.population_size}</span>
                {nonZero.map(([sev, n]) => (
                  <span key={sev}>
                    <span className="mx-1.5 text-slate-300">·</span>
                    {sev} <span className="font-mono">{n}</span>
                  </span>
                ))}
              </p>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
