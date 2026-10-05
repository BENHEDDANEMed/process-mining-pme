import { api } from '../lib/api.js'
import { useApi } from '../lib/useApi.js'
import { Async } from '../components/Async.jsx'
import { Card } from '../components/Card.jsx'
import { StatCard } from '../components/StatCard.jsx'
import { Histogram } from '../components/Histogram.jsx'
import { HBarChart } from '../components/HBarChart.jsx'
import { Gauge } from '../components/Gauge.jsx'
import { Table } from '../components/Table.jsx'
import { severityColor } from '../lib/statusColor.js'
import { fmtInt, fmtNum, fmtPct } from '../lib/format.js'

export function Conformance() {
  const { data, error } = useApi(api.conformance, [])

  return (
    <div className="space-y-6">
      <Async data={data} error={error}>
        {(d) => {
          const maxWait = Math.max(...d.bottlenecks.map((b) => b.avg_wait_hours), 1)
          return (
            <>
              <div className="grid grid-cols-1 md:grid-cols-[auto_1fr] gap-4 items-center bg-panel rounded-lg border border-hairline p-5">
                <Gauge
                  value={d.fitness_mean * 100}
                  max={100}
                  color={severityColor(d.fitness_mean, { goodMax: 0.3, watchMax: 0.6, invert: true })}
                  label="Fitness moyen"
                  size="compact"
                />
                <div className="grid grid-cols-2 gap-4">
                  <StatCard label="Fitness moyen (conformité)" value={fmtNum(d.fitness_mean, 3)} />
                  <StatCard label="Cas non conformes" value={`${fmtInt(d.non_conformant)} / ${fmtInt(d.total)}`} />
                </div>
              </div>

              <Card
                title="Distribution du fitness par cas"
                subtitle="Un fitness proche de 1 signifie que le cas suit fidèlement le processus modélisé."
              >
                <Histogram bins={d.fitness_histogram} xLabel="Fitness (0 = très dévié, 1 = conforme)" />
              </Card>

              <Card title="Cas les plus déviants">
                <Table
                  columns={[
                    { key: 'case_id', label: 'Cas' },
                    { key: 'trace_fitness', label: 'Fitness (conformité)', align: 'right' },
                    { key: 'is_fit', label: 'Conforme' },
                    { key: 'missing_tokens', label: 'Jetons manquants (écarts au modèle)', align: 'right' },
                    { key: 'remaining_tokens', label: 'Jetons non consommés', align: 'right' },
                  ]}
                  rows={d.deviants.map((r) => ({
                    ...r,
                    trace_fitness: fmtNum(r.trace_fitness, 3),
                    is_fit: r.is_fit ? '✓' : '',
                  }))}
                />
              </Card>

              <Card title="Goulots d'étranglement (temps d'attente moyen entre activités)">
                <HBarChart
                  data={d.bottlenecks.map((b) => ({ label: `${b.from_activity} →\n${b.to_activity}`, value: b.avg_wait_hours }))}
                  colorOf={(row) => severityColor(row.value / maxWait)}
                  valueFormatter={(v) => `${fmtInt(v)} h`}
                  labelWidth={260}
                  height={d.bottlenecks.length * 40}
                />
              </Card>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card title="Top rework par activité" subtitle="Part des cas qui repassent par cette activité (retour arrière / correction).">
                  <Table
                    columns={[
                      { key: 'activity', label: 'Activité' },
                      { key: 'cases_with_rework', label: 'Cas concernés', align: 'right' },
                      { key: 'rework_rate', label: 'Taux de rework', align: 'right' },
                    ]}
                    rows={d.rework.map((r) => ({ ...r, cases_with_rework: fmtInt(r.cases_with_rework), rework_rate: fmtPct(r.rework_rate) }))}
                  />
                </Card>
                <Card title="Charge par ressource" subtitle="Volume traité et durée moyenne des cas par ressource.">
                  <Table
                    columns={[
                      { key: 'resource', label: 'Ressource' },
                      { key: 'n_events', label: 'Nb. événements', align: 'right' },
                      { key: 'n_cases', label: 'Nb. cas traités', align: 'right' },
                      { key: 'avg_case_duration_hours', label: 'Durée moyenne des cas (h)', align: 'right' },
                    ]}
                    rows={d.resources.map((r) => ({
                      ...r,
                      n_events: fmtInt(r.n_events),
                      n_cases: fmtInt(r.n_cases),
                      avg_case_duration_hours: fmtNum(r.avg_case_duration_hours),
                    }))}
                  />
                </Card>
              </div>
            </>
          )
        }}
      </Async>
    </div>
  )
}
