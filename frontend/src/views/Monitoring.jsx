import { useState } from 'react'
import { api } from '../lib/api.js'
import { useApi } from '../lib/useApi.js'
import { Async } from '../components/Async.jsx'
import { Card } from '../components/Card.jsx'
import { StatCard } from '../components/StatCard.jsx'
import { Table } from '../components/Table.jsx'
import { Pagination } from '../components/Pagination.jsx'
import { HBarChart } from '../components/HBarChart.jsx'
import { TrendLine } from '../components/TrendLine.jsx'
import { AdvisoryBanner } from '../components/AdvisoryBanner.jsx'
import { fmtInt, fmtNum, fmtPct } from '../lib/format.js'

const LIMIT = 20
const BUCKET_COLOR = { LOW: 'var(--color-good)', MEDIUM: 'var(--color-watch)', HIGH: 'var(--color-storm)' }

export function Monitoring({ navigate }) {
  const { data: overview, error: overviewError } = useApi(api.monitoringOverview, [])
  const [offset, setOffset] = useState(0)
  const { data: highRisk, error: highRiskError } = useApi(
    () => api.monitoringHighRisk({ limit: LIMIT, offset }),
    [offset],
  )
  const [selectedCaseId, setSelectedCaseId] = useState(null)
  const { data: history, error: historyError } = useApi(
    () => (selectedCaseId ? api.monitoringHistory(selectedCaseId) : Promise.resolve(null)),
    [selectedCaseId],
  )

  return (
    <div className="space-y-6">
      <Async data={overview} error={overviewError}>
        {(o) => (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard label="Cas suivis" value={fmtInt(o.total_cases)} />
              <StatCard label="Risque faible" value={fmtInt(o.counts.LOW)} />
              <StatCard label="Risque moyen" value={fmtInt(o.counts.MEDIUM)} />
              <StatCard label="Risque élevé" value={fmtInt(o.counts.HIGH)} />
            </div>
            <Card
              title="Cas proches du seuil de retard"
              subtitle={`${fmtInt(o.sla_at_risk_count)} cas dont le temps écoulé + le temps restant prédit dépasserait le seuil de retard.`}
            >
              <HBarChart
                data={['LOW', 'MEDIUM', 'HIGH']
                  .filter((b) => o.avg_remaining_hours_by_bucket[b] != null)
                  .map((b) => ({ label: b, value: o.avg_remaining_hours_by_bucket[b] }))}
                colorOf={(row) => BUCKET_COLOR[row.label]}
                valueFormatter={(v) => `${fmtNum(v)} h`}
                height={140}
              />
            </Card>
          </>
        )}
      </Async>

      <Card title="Cas à risque élevé" subtitle={`Seuil configuré : probabilité de retard > ${fmtPct(overview?.thresholds?.high_min ?? 0.7)}.`}>
        <Async data={highRisk} error={highRiskError}>
          {(hr) => (
            <>
              <Table
                columns={[
                  { key: 'case_id', label: 'Cas' },
                  { key: 'proba_fmt', label: 'Probabilité de retard', align: 'right' },
                  { key: 'remaining_fmt', label: 'Temps restant prédit', align: 'right' },
                  { key: 'current_activity', label: 'Activité courante' },
                ]}
                rows={hr.cases.map((c) => ({
                  ...c,
                  proba_fmt: fmtPct(c.predicted_late_probability),
                  remaining_fmt: `${fmtNum(c.predicted_remaining_hours / 24)} j`,
                }))}
                onRowClick={(row) => setSelectedCaseId(row.case_id)}
              />
              <Pagination total={hr.total} limit={hr.limit} offset={hr.offset} onChange={setOffset} />
            </>
          )}
        </Async>
      </Card>

      {selectedCaseId && (
        <Card title={`Trajectoire de risque — ${selectedCaseId}`}>
          <Async data={history} error={historyError}>
            {(h) =>
              !h.available ? (
                <p className="text-sm text-ink-dim">Trajectoire indisponible ({h.reason ?? 'raison inconnue'}).</p>
              ) : (
                <>
                  <div className="mb-3">
                    <AdvisoryBanner>{h.note}</AdvisoryBanner>
                  </div>
                  <TrendLine
                    data={h.steps}
                    xKey="prefix_length"
                    yKey="proba_late"
                    xLabel="Étape (longueur de préfixe)"
                    yLabel="Probabilité de retard"
                    valueFormatter={(v) => fmtPct(v)}
                  />
                  {navigate && (
                    <button
                      onClick={() => navigate('prediction', 'current', { caseId: selectedCaseId })}
                      className="mt-3 text-sm text-instrument hover:text-ink cursor-pointer"
                    >
                      → Voir la prédiction détaillée pour ce cas
                    </button>
                  )}
                </>
              )
            }
          </Async>
        </Card>
      )}
    </div>
  )
}
