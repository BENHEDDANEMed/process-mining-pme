import { api } from '../lib/api.js'
import { useApi } from '../lib/useApi.js'
import { Async } from '../components/Async.jsx'
import { Card } from '../components/Card.jsx'
import { Table } from '../components/Table.jsx'
import { fmtInt } from '../lib/format.js'

const GRID_BG = {
  backgroundImage:
    'repeating-linear-gradient(0deg, var(--color-hairline) 0, var(--color-hairline) 1px, transparent 1px, transparent 32px), ' +
    'repeating-linear-gradient(90deg, var(--color-hairline) 0, var(--color-hairline) 1px, transparent 1px, transparent 32px)',
  backgroundColor: 'var(--color-ground)',
}

export function Process() {
  const { data, error } = useApi(api.process, [])

  return (
    <div className="space-y-6">
      <Async data={data} error={error}>
        {(d) => (
          <>
            <Card
              title="Carte du processus découvert (Inductive Miner)"
              subtitle="Modèle découvert sur les variantes couvrant 80% des cas (la version complète du log, avec 11 000+ variantes, produirait un modèle illisible)."
            >
              <p className="text-sm text-ink-dim mb-3 font-mono">
                Places : <b className="text-ink">{d.places}</b> · Transitions : <b className="text-ink">{d.transitions}</b> · Arcs :{' '}
                <b className="text-ink">{d.arcs}</b>
              </p>
              <div className="rounded-lg border border-hairline p-4" style={GRID_BG}>
                <div className="bg-[#f7f4ec] rounded shadow-lg overflow-hidden">
                  <div className="flex items-center justify-between px-3 py-1.5 border-b border-black/10">
                    <span className="text-xs font-mono uppercase tracking-widest text-black/50">Relevé instrument — modèle découvert</span>
                    <span className="text-xs font-mono text-black/40">Inductive Miner</span>
                  </div>
                  <div className="p-3">
                    <img src={d.image_url} alt="Réseau de Petri du processus découvert" className="w-full rounded" />
                  </div>
                </div>
              </div>
            </Card>

            <Card title="Top 10 des variantes de processus">
              <Table
                columns={[
                  { key: 'variant', label: "Variante (séquence d'activités)" },
                  { key: 'n_cases', label: 'Nombre de cas', align: 'right' },
                ]}
                rows={d.top_variants.map((v) => ({ ...v, n_cases: fmtInt(v.n_cases) }))}
              />
            </Card>
          </>
        )}
      </Async>
    </div>
  )
}
