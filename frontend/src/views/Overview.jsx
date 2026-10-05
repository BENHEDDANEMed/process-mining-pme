import { useState } from 'react'
import { api } from '../lib/api.js'
import { useApi } from '../lib/useApi.js'
import { Async } from '../components/Async.jsx'
import { Card } from '../components/Card.jsx'
import { StatCard } from '../components/StatCard.jsx'
import { HBarChart } from '../components/HBarChart.jsx'
import { Histogram } from '../components/Histogram.jsx'
import { Gauge } from '../components/Gauge.jsx'
import { statusColor } from '../lib/statusColor.js'
import { fmtInt, fmtNum, fmtPct } from '../lib/format.js'

export function Overview() {
  const { data, error } = useApi(api.overview, [])

  return (
    <div className="space-y-6">
      <Async data={data} error={error}>
        {(d) => (
          <>
            <HealthScore health={d.health} recommendations={d.recommendations} />

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard label="Nombre de cas" value={fmtInt(d.kpis.n_cases)} />
              <StatCard label="Durée moyenne" value={`${fmtNum(d.kpis.avg_case_duration_hours / 24)} j`} />
              <StatCard label="Durée médiane" value={`${fmtNum(d.kpis.median_case_duration_hours / 24)} j`} />
              <StatCard label="Taux de déviation" value={fmtPct(d.kpis.deviation_rate)} />
              <StatCard label="Nombre d'événements" value={fmtInt(d.kpis.n_events)} />
              <StatCard label="Nombre de variantes" value={fmtInt(d.kpis.n_variants)} />
              <StatCard label="Taux de rework moyen" value={fmtPct(d.kpis.overall_rework_rate)} />
              <StatCard label="Fitness moyen" value={fmtNum(d.kpis.avg_fitness, 3)} />
            </div>

            <Card title="Distribution de la durée des cas" subtitle="Jours, tronquée au 95e percentile">
              <Histogram bins={d.duration_histogram} xLabel="Durée (j)" />
            </Card>

            <Card title="Activités les plus fréquentes">
              <HBarChart data={d.top_activities} valueFormatter={fmtInt} height={d.top_activities.length * 30} />
            </Card>
          </>
        )}
      </Async>
    </div>
  )
}

function HealthScore({ health, recommendations }) {
  const [open, setOpen] = useState(false)
  const color = statusColor(health.status)
  const dims = Object.entries(health.scores)
    .filter(([, v]) => v !== null)
    .map(([key, value]) => ({ label: health.labels[key], value }))
    .sort((a, b) => a.value - b.value)

  return (
    <div
      className="rounded-lg border border-hairline p-5"
      style={{ background: `radial-gradient(ellipse 120% 100% at 0% 0%, color-mix(in srgb, ${color} 16%, var(--color-panel)), var(--color-panel) 70%)` }}
    >
      <h3 className="text-base font-semibold text-ink">Process Health</h3>
      <p className="text-sm text-ink-dim mt-1 mb-4">
        Synthèse des analyses des autres onglets en un score unique. Une dimension non disponible pour ce
        processus est exclue du calcul, et les poids des autres sont renormalisés.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-4 items-center">
        <div className="flex flex-col items-center">
          <Gauge value={health.overall_score} max={100} color={color} size="hero" />
          <div className="text-sm font-bold font-mono tracking-wide" style={{ color }}>
            {health.status}
          </div>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-4 justify-center md:justify-start">
          {dims.map((d) => (
            <Gauge key={d.label} value={d.value} max={108} color={color} label={d.label} size="compact" />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mt-4">
        <div>
          <div className="text-xs text-ink-dim uppercase tracking-wide">Point faible</div>
          <div className="text-lg font-semibold text-ink">{health.main_weakness ?? '-'}</div>
        </div>
        <div>
          <div className="text-xs text-ink-dim uppercase tracking-wide">Point fort</div>
          <div className="text-lg font-semibold text-ink">{health.main_strength ?? '-'}</div>
        </div>
      </div>

      <div className="mt-4 bg-instrument/10 text-ink text-sm rounded-lg p-3 border border-instrument/30">{health.interpretation}</div>

      {recommendations?.length > 0 && (
        <div className="mt-3">
          <button onClick={() => setOpen((o) => !o)} className="text-sm text-ink-dim hover:text-ink cursor-pointer">
            {open ? '▾' : '▸'} Recommandation associée (Business Analysis)
          </button>
          {open && (
            <ul className="mt-2 text-sm text-ink list-disc pl-5 space-y-1">
              {recommendations.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {health.missing_dimensions?.length > 0 && (
        <p className="text-xs text-ink-dim mt-3">
          Non disponible pour ce processus : {health.missing_dimensions.map((d) => health.labels[d]).join(', ')}.
        </p>
      )}
    </div>
  )
}
