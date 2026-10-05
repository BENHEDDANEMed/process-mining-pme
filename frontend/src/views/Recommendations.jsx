import { api } from '../lib/api.js'
import { useApi } from '../lib/useApi.js'
import { Async } from '../components/Async.jsx'
import { Card } from '../components/Card.jsx'
import { Table } from '../components/Table.jsx'
import { AdvisoryBanner } from '../components/AdvisoryBanner.jsx'

export function Recommendations() {
  const { data, error } = useApi(api.recommendations, [])

  return (
    <div className="space-y-6">
      <Async data={data} error={error}>
        {(d) => (
          <>
            <Card title="Bulletin de recommandations" subtitle="Règles générées automatiquement à partir des KPI de process mining et de performance.">
              {d.recommendations.length === 0 ? (
                <p className="text-sm text-ink-dim">Aucune recommandation déclenchée sur les seuils actuels.</p>
              ) : (
                <div className="space-y-2">
                  {d.recommendations.map((r, i) => (
                    <AdvisoryBanner key={i}>{r}</AdvisoryBanner>
                  ))}
                </div>
              )}
            </Card>

            <Card title="Problèmes détectés et impact">
              {d.problems.length === 0 ? (
                <p className="text-sm text-ink-dim">Aucun problème majeur détecté sur les seuils actuels.</p>
              ) : (
                <Table
                  columns={[
                    { key: 'probleme', label: 'Problème', wrap: true },
                    { key: 'impact', label: 'Impact', wrap: true },
                  ]}
                  rows={d.problems}
                />
              )}
            </Card>
          </>
        )}
      </Async>
    </div>
  )
}
