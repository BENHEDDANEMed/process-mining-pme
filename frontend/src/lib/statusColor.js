export const STATUS_COLORS = {
  EXCELLENT: 'var(--color-good)',
  GOOD: 'var(--color-good)',
  WARNING: 'var(--color-watch)',
  CRITICAL: 'var(--color-storm)',
  UNKNOWN: 'var(--color-neutral)',
}

export const statusColor = (status) => STATUS_COLORS[status] ?? STATUS_COLORS.UNKNOWN

// Severity from a 0-1 ratio (risk probabilities, deviation/rework rates).
// Lower is better by default; pass `invert: true` when higher is better (e.g. fitness).
export function severityColor(ratio, { goodMax = 0.3, watchMax = 0.6, invert = false } = {}) {
  const r = invert ? 1 - ratio : ratio
  if (r <= goodMax) return STATUS_COLORS.GOOD
  if (r <= watchMax) return STATUS_COLORS.WARNING
  return STATUS_COLORS.CRITICAL
}
