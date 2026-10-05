import { fmtInt } from '../lib/format.js'

// Prev/Next + "X-Y sur Z" — pas d'entree de page directe, inutile pour un
// jeu de donnees de cette taille (~250k lignes) ou l'on avance sequentiellement.
export function Pagination({ total, limit, offset, onChange }) {
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + limit, total)

  return (
    <div className="flex items-center justify-between text-sm text-ink-dim mt-3">
      <span className="font-mono">
        {fmtInt(from)}–{fmtInt(to)} sur {fmtInt(total)}
      </span>
      <div className="flex gap-2">
        <button
          onClick={() => onChange(Math.max(0, offset - limit))}
          disabled={offset <= 0}
          className="px-3 py-1 rounded-lg border border-hairline text-ink-dim hover:text-ink hover:border-instrument disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
        >
          Précédent
        </button>
        <button
          onClick={() => onChange(offset + limit)}
          disabled={offset + limit >= total}
          className="px-3 py-1 rounded-lg border border-hairline text-ink-dim hover:text-ink hover:border-instrument disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
        >
          Suivant
        </button>
      </div>
    </div>
  )
}
