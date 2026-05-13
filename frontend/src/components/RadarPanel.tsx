import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from 'recharts'
import type { SubScore } from '../types'

interface Props {
  subScores: SubScore[]
}

export default function RadarPanel({ subScores }: Props) {
  const data = subScores.map((s) => ({
    dimension: s.dimension.charAt(0).toUpperCase() + s.dimension.slice(1),
    score: Number(s.score.toFixed(1)),
  }))

  return (
    <div className="rounded-2xl bg-white border border-slate-200 p-6 shadow-sm">
      <h3 className="text-sm font-semibold text-slate-700 mb-1">Dimension radar</h3>
      <p className="text-xs text-slate-500 mb-4">0 = worst, 100 = perfect</p>
      <ResponsiveContainer width="100%" height={320}>
        <RadarChart data={data} margin={{ top: 8, right: 24, bottom: 8, left: 24 }}>
          <PolarGrid stroke="#e2e8f0" />
          <PolarAngleAxis
            dataKey="dimension"
            tick={{ fontSize: 11, fill: '#64748b', fontWeight: 500 }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: '#94a3b8' }}
            tickCount={6}
          />
          <Radar
            name="Score"
            dataKey="score"
            stroke="#f59e0b"
            fill="#f59e0b"
            fillOpacity={0.35}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
