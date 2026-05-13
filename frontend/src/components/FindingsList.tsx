import type { Finding, Severity } from '../types'

interface Props {
  findings: Finding[]
}

const SEV_BADGE: Record<Severity, string> = {
  info: 'bg-slate-100 text-slate-700 ring-slate-200',
  warn: 'bg-amber-100 text-amber-800 ring-amber-200',
  error: 'bg-orange-100 text-orange-800 ring-orange-200',
  critical: 'bg-red-100 text-red-800 ring-red-200',
}

const SEV_ORDER: Record<Severity, number> = {
  critical: 0,
  error: 1,
  warn: 2,
  info: 3,
}

export default function FindingsList({ findings }: Props) {
  if (findings.length === 0) {
    return (
      <div className="rounded-2xl bg-white border border-slate-200 p-8 text-center shadow-sm">
        <p className="text-slate-500">No findings. Clean model.</p>
      </div>
    )
  }

  const byDim = new Map<string, Finding[]>()
  for (const f of findings) {
    if (!byDim.has(f.dimension)) byDim.set(f.dimension, [])
    byDim.get(f.dimension)!.push(f)
  }
  for (const arr of byDim.values()) {
    arr.sort((a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity])
  }

  // Order dimensions by worst severity first
  const dims = [...byDim.entries()].sort((a, b) => {
    const worstA = Math.min(...a[1].map((f) => SEV_ORDER[f.severity]))
    const worstB = Math.min(...b[1].map((f) => SEV_ORDER[f.severity]))
    return worstA - worstB
  })

  return (
    <div className="rounded-2xl bg-white border border-slate-200 p-6 shadow-sm">
      <h3 className="text-sm font-semibold text-slate-700 mb-1">
        Findings ({findings.length})
      </h3>
      <p className="text-xs text-slate-500 mb-5">
        Grouped by dimension · sorted by severity
      </p>
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
              {items.map((f, i) => (
                <li
                  key={i}
                  className="flex gap-3 px-4 py-3 border-t border-slate-100 first:border-t-0"
                >
                  <span
                    className={`shrink-0 inline-flex items-center px-2 py-0.5 rounded ring-1 ring-inset text-[10px] font-bold uppercase tracking-wider h-fit mt-0.5 ${SEV_BADGE[f.severity]}`}
                  >
                    {f.severity}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-900 leading-relaxed">{f.message}</p>
                    {f.remediation && (
                      <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                        → {f.remediation}
                      </p>
                    )}
                    <p className="text-[10px] font-mono text-slate-400 mt-1">{f.rule_id}</p>
                  </div>
                </li>
              ))}
            </ul>
          </details>
        ))}
      </div>
    </div>
  )
}
