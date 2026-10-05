const TICKS = {
  backgroundImage: 'repeating-linear-gradient(90deg, var(--color-hairline) 0, var(--color-hairline) 1px, transparent 1px, transparent 6px)',
}

// Label plate styled after an instrument readout: tick strip under the label,
// mono digits for the reading.
export function StatCard({ label, value }) {
  return (
    <div className="relative bg-panel rounded-lg border border-hairline px-4 py-3 overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-0.5 bg-instrument" />
      <div className="text-xs font-medium text-ink-dim uppercase tracking-wide">{label}</div>
      <div className="h-1 mt-1" style={TICKS} />
      <div className="text-2xl font-bold font-mono text-ink mt-1">{value}</div>
    </div>
  )
}
