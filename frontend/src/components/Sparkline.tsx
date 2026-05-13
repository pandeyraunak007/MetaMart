// Tiny inline sparkline used by Portfolio rows + Versions tab.
// Plots a series of numeric values into a fixed-size SVG. Values are clamped
// to the visible band; assumed quality-score domain is 0..100 by default.

interface Props {
  values: number[]            // newest-first or oldest-first — see `oldestFirst`
  oldestFirst?: boolean       // default false: caller passes newest-first (matches storage)
  width?: number
  height?: number
  domain?: [number, number]
  stroke?: string
  fill?: string
  className?: string
  title?: string
}

export default function Sparkline({
  values,
  oldestFirst = false,
  width = 80,
  height = 22,
  domain = [0, 100],
  stroke = '#f59e0b',
  fill = 'rgba(245, 158, 11, 0.15)',
  className,
  title,
}: Props) {
  if (!values.length) {
    return (
      <span
        className={`inline-block text-xs text-slate-300 font-mono ${className ?? ''}`}
        style={{ width, height, lineHeight: `${height}px` }}
      >
        —
      </span>
    )
  }

  const series = oldestFirst ? values : [...values].reverse()
  const [min, max] = domain
  const span = Math.max(max - min, 0.0001)
  const pad = 2
  const innerW = width - pad * 2
  const innerH = height - pad * 2

  const points = series.map((v, i) => {
    const x = series.length === 1
      ? width / 2
      : pad + (i / (series.length - 1)) * innerW
    const clamped = Math.max(min, Math.min(max, v))
    const y = pad + innerH - ((clamped - min) / span) * innerH
    return [x, y] as const
  })

  if (points.length === 1) {
    const [x, y] = points[0]
    return (
      <svg width={width} height={height} className={className} role="img">
        {title && <title>{title}</title>}
        <circle cx={x} cy={y} r={2.5} fill={stroke} />
      </svg>
    )
  }

  const polyline = points.map(([x, y]) => `${x},${y}`).join(' ')
  const areaPath =
    `M ${points[0][0]},${height - pad} ` +
    points.map(([x, y]) => `L ${x},${y}`).join(' ') +
    ` L ${points[points.length - 1][0]},${height - pad} Z`

  const last = points[points.length - 1]

  return (
    <svg width={width} height={height} className={className} role="img">
      {title && <title>{title}</title>}
      <path d={areaPath} fill={fill} stroke="none" />
      <polyline
        points={polyline}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={last[0]} cy={last[1]} r={1.8} fill={stroke} />
    </svg>
  )
}
