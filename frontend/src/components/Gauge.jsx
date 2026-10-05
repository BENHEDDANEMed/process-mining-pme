import { useEffect, useState } from 'react'

// Semicircular instrument dial. Needle sweeps in once on mount/value change.
// ponytail: one gauge component reused at hero size (Process Health Score) and
// compact size (secondary readouts); no per-view dial variants.
export function Gauge({ value, max = 100, color, label, size = 'hero', unit = '' }) {
  const [display, setDisplay] = useState(0)

  useEffect(() => {
    const id = requestAnimationFrame(() => setDisplay(value))
    return () => cancelAnimationFrame(id)
  }, [value])

  const pct = Math.max(0, Math.min(1, max ? display / max : 0))
  const isHero = size === 'hero'
  const r = isHero ? 84 : 42
  const c = isHero ? 100 : 50
  const stroke = isHero ? 14 : 8
  const circumference = Math.PI * r
  const arcPath = `M ${c - r} ${c} A ${r} ${r} 0 0 1 ${c + r} ${c}`
  const angle = -90 + pct * 180

  return (
    <div className="flex flex-col items-center">
      <svg viewBox={`0 0 ${c * 2} ${c + stroke}`} width={isHero ? 220 : 112} height={isHero ? 120 : 60}>
        <path d={arcPath} fill="none" stroke="var(--color-hairline)" strokeWidth={stroke} strokeLinecap="round" />
        <path
          d={arcPath}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          style={{
            strokeDasharray: circumference,
            strokeDashoffset: circumference * (1 - pct),
            transition: 'stroke-dashoffset 900ms cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        />
        <line
          x1={c}
          y1={c}
          x2={c}
          y2={c - r + stroke}
          stroke={color}
          strokeWidth={isHero ? 3 : 2}
          strokeLinecap="round"
          style={{
            transformOrigin: `${c}px ${c}px`,
            transform: `rotate(${angle}deg)`,
            transition: 'transform 900ms cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        />
        <circle cx={c} cy={c} r={isHero ? 6 : 4} fill={color} />
      </svg>
      <div className={isHero ? 'text-5xl font-bold font-mono -mt-1' : 'text-xl font-bold font-mono'} style={{ color }}>
        {Math.round(display)}
        {unit && <span className="text-base font-normal text-ink-dim">{unit}</span>}
      </div>
      {label && <div className="text-xs uppercase tracking-wide text-ink-dim mt-1 text-center">{label}</div>}
    </div>
  )
}
