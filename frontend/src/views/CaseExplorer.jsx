import { useState } from 'react'
import { api } from '../lib/api.js'
import { useApi } from '../lib/useApi.js'
import { Async } from '../components/Async.jsx'
import { Card } from '../components/Card.jsx'
import { Table } from '../components/Table.jsx'
import { Pagination } from '../components/Pagination.jsx'
import { fmtDate, fmtInt, fmtNum, fmtPct } from '../lib/format.js'

const LIMIT = 20

export function CaseExplorer({ navigate, navContext }) {
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [variantId, setVariantId] = useState(() => navContext?.variantId ?? null)
  const [selectedCaseId, setSelectedCaseId] = useState(() => navContext?.caseId ?? null)

  const params = { q: query, limit: LIMIT, offset }
  if (variantId != null) params.variant_id = variantId
  const { data, error } = useApi(() => api.caseList(params), [query, offset, variantId])

  const { data: detail, error: detailError } = useApi(
    () => (selectedCaseId ? api.caseDetail(selectedCaseId) : Promise.resolve(null)),
    [selectedCaseId],
  )

  return (
    <div className="space-y-6">
      <Card title="Explorateur de cas" subtitle="Recherche sur l'identifiant ou les attributs métier (fournisseur, catégorie, société...).">
        <div className="flex flex-wrap items-center gap-3 mb-3">
          <input
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setOffset(0)
            }}
            placeholder="ex. vendorID_0002"
            className="border border-hairline rounded-lg px-3 py-2 text-sm w-full max-w-sm bg-panel-raised text-ink font-mono placeholder:text-ink-dim"
          />
          {variantId != null && (
            <button
              onClick={() => {
                setVariantId(null)
                setOffset(0)
              }}
              className="text-sm text-instrument hover:text-ink cursor-pointer font-mono"
            >
              Variante #{variantId} ✕
            </button>
          )}
        </div>

        <Async data={data} error={error}>
          {(d) => (
            <>
              <Table
                columns={[
                  { key: 'case_id', label: 'Cas' },
                  { key: 'vendor', label: 'Fournisseur' },
                  { key: 'duration_days', label: 'Durée (j)', align: 'right' },
                  { key: 'n_events', label: 'Événements', align: 'right' },
                  { key: 'rework_count', label: 'Rework', align: 'right' },
                  { key: 'conforme', label: 'Conforme' },
                  { key: 'risque', label: 'Risque prédit' },
                ]}
                rows={d.cases.map((c) => ({
                  ...c,
                  duration_days: fmtNum(c.duration_hours / 24),
                  conforme: c.is_fit === null ? '—' : c.is_fit ? '✓' : '✗',
                  risque: c.predicted_label ?? 'non échantillonné',
                }))}
                onRowClick={(row) => setSelectedCaseId(row.case_id)}
              />
              <Pagination total={d.total} limit={d.limit} offset={d.offset} onChange={setOffset} />
            </>
          )}
        </Async>
      </Card>

      {selectedCaseId && (
        <Async data={detail} error={detailError}>
          {(d) => (
            <Card title={`Cas ${d.case.case_id}`} subtitle={d.deviation_note}>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Table
                  columns={[
                    { key: 'label', label: 'Indicateur' },
                    { key: 'value', label: 'Valeur' },
                  ]}
                  rows={[
                    { label: 'Fournisseur', value: d.case.vendor },
                    { label: 'Catégorie', value: d.case.item_category },
                    { label: 'Société', value: d.case.company },
                    { label: 'Durée', value: `${fmtNum(d.case.duration_hours / 24)} j` },
                    { label: 'Événements', value: fmtInt(d.case.n_events) },
                    { label: 'Rework', value: fmtInt(d.case.rework_count) },
                    { label: 'Clôturé', value: d.case.closed ? 'Oui' : 'Non' },
                    { label: 'Fitness', value: d.case.trace_fitness != null ? fmtNum(d.case.trace_fitness, 3) : '—' },
                    {
                      label: 'Prédiction',
                      value: d.prediction
                        ? `${d.prediction.predicted_label} (${fmtPct(d.prediction.predicted_late_probability)})`
                        : 'non échantillonné pour le ML',
                    },
                  ]}
                />
                <div>
                  <div className="text-xs text-ink-dim uppercase tracking-wide mb-2">Chronologie</div>
                  <Table
                    columns={[
                      { key: 'seq', label: '#', align: 'right' },
                      { key: 'activity', label: 'Activité', wrap: true },
                      { key: 'attente', label: 'Attente', align: 'right' },
                      { key: 'quand', label: 'Quand', wrap: true },
                    ]}
                    rows={d.timeline.map((t) => ({
                      seq: t.seq,
                      activity: `${t.activity}${t.is_repeat ? ' ↻' : ''}${t.is_rare ? ' ⚠' : ''}`,
                      attente: `${fmtNum(t.wait_hours_since_prev)} h`,
                      quand: fmtDate(t.timestamp),
                    }))}
                  />
                </div>
              </div>
              {navigate && (
                <button
                  onClick={() => navigate('prediction', 'current', { caseId: d.case.case_id })}
                  className="mt-4 text-sm text-instrument hover:text-ink cursor-pointer"
                >
                  → Voir la prédiction détaillée pour ce cas
                </button>
              )}
            </Card>
          )}
        </Async>
      )}
    </div>
  )
}
