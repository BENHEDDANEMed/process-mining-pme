// Recommendation bulletins carry no per-item severity from the API (rule-triggered
// strings, not ranked) -- one consistent advisory tone, not fabricated severity.
export function AdvisoryBanner({ children }) {
  return (
    <div className="bg-watch/10 border border-watch/30 rounded-lg p-3 flex items-start gap-3">
      <span className="text-watch font-mono text-xs font-bold uppercase tracking-wide shrink-0 mt-0.5">Avis</span>
      <p className="text-sm text-ink">{children}</p>
    </div>
  )
}
