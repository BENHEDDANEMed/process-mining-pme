export function Async({ data, error, children }) {
  if (error) return <div className="text-storm text-sm p-4">Erreur de chargement : {error.message}</div>
  if (!data) return <div className="text-ink-dim text-sm p-4 animate-pulse font-mono">Relevé en cours…</div>
  return children(data)
}
