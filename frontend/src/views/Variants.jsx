import { useState } from 'react'
import { api } from '../lib/api.js'
import { useApi } from '../lib/useApi.js'
import { Async } from '../components/Async.jsx'
import { Card } from '../components/Card.jsx'
import { Table } from '../components/Table.jsx'
import { fmtInt, fmtNum, fmtPct } from '../lib/format.js'

const TOP_N = 20

export function Variants({ navigate }) {
  const { data, error } = useApi(api.variants, [])
  const [selected, setSelected] = useState(null)

  return (
    <div className="space-y-6">
      <Card
        title="Variantes du processus"
        subtitle={`Top ${TOP_N} séquences les plus fréquentes ; le reste est regroupé sous "Autres".`}
      >
        <Async data={data} error={error}>
          {(d) => (
            <Table
              columns={[
                { key: 'variant_id', label: 'ID', align: 'right' },
                { key: 'n_cases', label: 'Cas', align: 'right' },
                { key: 'frequency_pct', label: '%', align: 'right' },
                { key: 'avg_duration_days', label: 'Durée moy. (j)', align: 'right' },
                { key: 'rework_rate', label: 'Rework', align: 'right' },
                { key: 'conformance_rate', label: 'Conformité', align: 'right' },
              ]}
              rows={d.variants.map((v) => ({
                ...v,
                variant_id: v.variant_id === -1 ? 'Autres' : v.variant_id,
                avg_duration_days: v.avg_duration_hours != null ? fmtNum(v.avg_duration_hours / 24) : '—',
                rework_rate: v.rework_rate != null ? fmtPct(v.rework_rate) : '—',
                conformance_rate: v.conformance_rate != null ? fmtPct(v.conformance_rate) : '—',
                frequency_pct: `${fmtNum(v.frequency_pct)} %`,
                n_cases: fmtInt(v.n_cases),
              }))}
              onRowClick={(row) => {
                const v = d.variants.find((x) => x.variant_id === row.variant_id || (row.variant_id === 'Autres' && x.variant_id === -1))
                if (v?.sequence) setSelected(v)
              }}
            />
          )}
        </Async>
      </Card>

      {selected && (
        <Card title={`Variante #${selected.variant_id}`} subtitle={`${fmtInt(selected.n_cases)} cas, ${fmtNum(selected.frequency_pct)} % du total.`}>
          <div className="flex flex-wrap items-center gap-2 mb-4">
            {selected.sequence.map((activite, i) => (
              <span key={i} className="flex items-center gap-2">
                <span className="px-2 py-1 rounded-lg border border-hairline bg-panel-raised text-xs font-mono text-ink">{activite}</span>
                {i < selected.sequence.length - 1 && <span className="text-ink-faint">→</span>}
              </span>
            ))}
          </div>
          {navigate && (
            <button
              onClick={() => navigate('cases', null, { variantId: selected.variant_id })}
              className="text-sm text-instrument hover:text-ink cursor-pointer"
            >
              → Voir les cas de cette variante dans l'explorateur
            </button>
          )}
        </Card>
      )}
    </div>
  )
}
