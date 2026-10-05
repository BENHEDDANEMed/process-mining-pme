import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import { useApi } from '../lib/useApi.js'
import { Async } from '../components/Async.jsx'
import { Card } from '../components/Card.jsx'
import { StatCard } from '../components/StatCard.jsx'
import { Table } from '../components/Table.jsx'
import { Gauge } from '../components/Gauge.jsx'
import { HBarChart } from '../components/HBarChart.jsx'
import { AdvisoryBanner } from '../components/AdvisoryBanner.jsx'
import { severityColor } from '../lib/statusColor.js'
import { fmtNum, fmtPct } from '../lib/format.js'

// Positif = pousse la prediction vers plus de risque/plus de temps ; negatif
// = vers moins. Meme convention pour le classifieur et le regresseur.
const impactColor = (value) => (value >= 0 ? 'var(--color-storm)' : 'var(--color-good)')

function ExplainChart({ title, explanation }) {
  if (!explanation) return <p className="text-sm text-ink-dim">Explication indisponible pour ce modèle.</p>
  const data = explanation.contributions.map((c) => ({ label: c.feature, value: c.impact }))
  return (
    <div>
      <div className="text-xs text-ink-dim uppercase tracking-wide mb-2">{title}</div>
      <HBarChart data={data} colorOf={(row) => impactColor(row.value)} valueFormatter={(v) => fmtNum(v, 3)} height={data.length * 30} />
    </div>
  )
}

const inputClass =
  'border border-hairline rounded-lg px-3 py-2 text-sm w-full max-w-sm bg-panel-raised text-ink font-mono placeholder:text-ink-dim'

export function Prediction({ navContext }) {
  const [query, setQuery] = useState('')
  const { data: cases, error: casesError } = useApi(() => api.cases(query), [query])
  // Preselection venant d'un lien croise (ex. Explorateur de cas) : lue une
  // seule fois au montage, la vue garde ensuite sa propre selection.
  const [caseId, setCaseId] = useState(() => navContext?.caseId ?? null)
  const { data: caseInfo, error: caseError } = useApi(() => (caseId ? api.caseSteps(caseId) : Promise.resolve(null)), [caseId])
  const [step, setStep] = useState(null)
  const { data: pred, error: predError } = useApi(
    () => (caseId && step ? api.prediction(caseId, step) : Promise.resolve(null)),
    [caseId, step],
  )
  const { data: explain, error: explainError } = useApi(
    () => (caseId && step ? api.explain(caseId, step) : Promise.resolve(null)),
    [caseId, step],
  )
  const { data: rootCause, error: rootCauseError } = useApi(api.rootCause, [])

  useEffect(() => {
    if (cases?.length && !caseId) setCaseId(cases[0])
  }, [cases, caseId])

  useEffect(() => {
    if (caseInfo) setStep(caseInfo.n_steps)
  }, [caseInfo])

  return (
    <div className="space-y-6">
      <Card title="Bulletin de prévision" subtitle="Prédiction sur un cas en cours, à l'étape choisie.">
        <Async data={cases} error={casesError}>
          {(list) => (
            <div className="space-y-4">
              <div>
                <label className="text-sm text-ink-dim block mb-1">
                  Rechercher un cas <span className="text-ink-dim">(~60 000 cas, tapez pour filtrer)</span>
                </label>
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="ex. 2000000003"
                  className={`${inputClass} mb-2`}
                />
                <select
                  value={caseId ?? ''}
                  onChange={(e) => {
                    setCaseId(e.target.value)
                    setStep(null)
                  }}
                  className={inputClass}
                >
                  {/* Le cas courant peut venir d'ailleurs (ex. Explorateur de cas) et
                      ne pas figurer dans les 50 premiers résultats de la recherche
                      rapide : sans lui comme option, le <select> afficherait le
                      premier de la liste au lieu du cas réellement sélectionné. */}
                  {[...new Set([caseId, ...list].filter(Boolean))].map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>

              <Async data={caseInfo} error={caseError}>
                {(info) => (
                  <div>
                    <label className="text-sm text-ink-dim block mb-1">
                      Étape du cas (longueur de préfixe) — <b className="text-ink font-mono">{step}</b> / {info.n_steps}
                    </label>
                    <input
                      type="range"
                      min={1}
                      max={info.n_steps}
                      value={step ?? info.n_steps}
                      onChange={(e) => setStep(Number(e.target.value))}
                      className="w-full max-w-lg"
                    />
                  </div>
                )}
              </Async>
            </div>
          )}
        </Async>
      </Card>

      <Async data={pred} error={predError}>
        {(p) => (
          <>
            <Card title="État du cas à cette étape">
              <Table
                columns={[
                  { key: 'label', label: 'Indicateur' },
                  { key: 'value', label: 'Valeur' },
                ]}
                rows={Object.entries(p.state).map(([label, value]) => ({ label, value }))}
              />
            </Card>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card title="Risque de retard" subtitle={`Un cas est dit en retard au-delà de ${p.late_threshold_days} jours de durée totale.`}>
                <div className="flex items-center gap-4">
                  <Gauge value={p.proba.LATE * 100} max={100} color={severityColor(p.proba.LATE)} unit="%" size="compact" />
                  <div className="text-xs text-ink-dim uppercase tracking-wide">Probabilité de retard</div>
                </div>
                <div className="mt-3">
                  <Table
                    columns={[
                      { key: 'classe', label: 'Classe' },
                      { key: 'probabilite', label: 'Probabilité', align: 'right' },
                    ]}
                    rows={Object.entries(p.proba)
                      .sort((a, b) => b[1] - a[1])
                      .map(([classe, v]) => ({ classe, probabilite: fmtPct(v) }))}
                  />
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3">
                  <StatCard label={`Prédiction (seuil ${fmtNum(p.decision_threshold, 2)})`} value={p.predicted_label} />
                  <StatCard label="Issue réelle (a posteriori)" value={p.actual_label} />
                </div>
              </Card>

              <Card title="Temps restant estimé">
                <div className="space-y-3">
                  <StatCard label="Temps restant prédit" value={`${fmtNum(p.predicted_remaining_hours)} h (${fmtNum(p.predicted_remaining_hours / 24)} j)`} />
                  <StatCard label="Temps restant réel" value={`${fmtNum(p.actual_remaining_hours)} h (${fmtNum(p.actual_remaining_hours / 24)} j)`} />
                </div>
              </Card>
            </div>

            <Card
              title="Pourquoi cette prédiction ?"
              subtitle="Contribution de chaque facteur à la prédiction (SHAP) — rouge pousse vers plus de risque/temps, vert vers moins. Le sens et l'ampleur relative sont fiables ; l'unité brute du modèle ne se lit pas en points de pourcentage ou en heures."
            >
              <Async data={explain} error={explainError}>
                {(e) =>
                  !e.available ? (
                    <p className="text-sm text-ink-dim">Explication indisponible pour ce cas ({e.reason ?? 'raison inconnue'}).</p>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <ExplainChart title="Risque de retard" explanation={e.classifier} />
                      <ExplainChart title="Temps restant" explanation={e.regressor} />
                    </div>
                  )
                }
              </Async>
            </Card>
          </>
        )}
      </Async>

      <Card title="Analyse des causes probables" subtitle="Comparaison globale des cas en retard vs à l'heure sur l'historique — un facteur associé, pas une cause démontrée.">
        <Async data={rootCause} error={rootCauseError}>
          {(rc) =>
            !rc.available ? (
              <p className="text-sm text-ink-dim">Analyse indisponible (aucun échantillon avec étiquette connue).</p>
            ) : (
              <>
                <Table
                  columns={[
                    { key: 'feature', label: 'Facteur' },
                    { key: 'categorie', label: 'Catégorie dominante' },
                    { key: 'ecart_fmt', label: 'Écart (en retard vs à l’heure)', align: 'right' },
                  ]}
                  rows={rc.comparisons.map((c) => ({
                    ...c,
                    categorie: c.categorie ?? '—',
                    ecart_fmt: c.type === 'categoriel' ? fmtPct(Math.abs(c.ecart)) : fmtNum(c.ecart),
                  }))}
                />
                <div className="mt-3">
                  <AdvisoryBanner>{rc.disclaimer}</AdvisoryBanner>
                </div>
              </>
            )
          }
        </Async>
      </Card>
    </div>
  )
}
