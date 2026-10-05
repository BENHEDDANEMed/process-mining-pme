import { useState } from 'react'
import neomoritLogo from './assets/neomorit-logo.jpg'
import { Overview } from './views/Overview.jsx'
import { Process } from './views/Process.jsx'
import { Variants } from './views/Variants.jsx'
import { Conformance } from './views/Conformance.jsx'
import { Prediction } from './views/Prediction.jsx'
import { Monitoring } from './views/Monitoring.jsx'
import { CaseExplorer } from './views/CaseExplorer.jsx'
import { Recommendations } from './views/Recommendations.jsx'

const TABS = [
  { id: 'overview', label: "Vue d'ensemble", view: Overview },
  {
    id: 'process',
    label: 'Processus',
    subtabs: [
      { id: 'discovery', label: 'Découverte', view: Process },
      { id: 'variants', label: 'Variantes', view: Variants },
    ],
  },
  { id: 'conformance', label: 'Conformité & Performance', view: Conformance },
  {
    id: 'prediction',
    label: 'Prédiction',
    subtabs: [
      { id: 'current', label: 'Cas courant', view: Prediction },
      { id: 'monitoring', label: 'Monitoring', view: Monitoring },
    ],
  },
  { id: 'cases', label: 'Explorateur de cas', view: CaseExplorer },
  { id: 'recommendations', label: 'Recommandations', view: Recommendations },
]

export default function App() {
  const [active, setActive] = useState(TABS[0].id)
  const [subActive, setSubActive] = useState({})
  const [navContext, setNavContext] = useState({})

  // Navigation croisee entre vues (ex. Variantes -> Explorateur de cas) sans
  // routeur : un simple contexte pousse a la vue cible, lue une fois au montage.
  const navigate = (tabId, subId, ctx = {}) => {
    setActive(tabId)
    if (subId) setSubActive((s) => ({ ...s, [tabId]: subId }))
    setNavContext(ctx)
  }

  const activeTab = TABS.find((t) => t.id === active)
  const activeSub = activeTab.subtabs
    ? activeTab.subtabs.find((s) => s.id === subActive[active]) ?? activeTab.subtabs[0]
    : null
  const ActiveView = activeSub ? activeSub.view : activeTab.view

  return (
    <div className="min-h-screen bg-ground">
      <header className="bg-panel border-b border-hairline">
        <div className="max-w-6xl mx-auto px-6 pt-5 pb-3 flex items-center gap-4">
          <img src={neomoritLogo} alt="NeoMorIT" className="h-9 w-9 rounded-md object-cover" />
          <div className="w-px h-8 bg-hairline" />
          <div>
            <h1 className="text-xl font-semibold text-ink tracking-tight">
              Process Mining PME <span className="text-ink-dim font-normal">— Purchase-to-Pay (BPI Challenge 2019)</span>
            </h1>
            <p className="text-sm text-ink-dim mt-0.5">
              Station de relevé du processus — conditions mesurées en direct, prévision en vue dédiée.
            </p>
          </div>
        </div>
        <nav className="max-w-6xl mx-auto px-6 flex gap-1 overflow-x-auto">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => navigate(t.id, null)}
              className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors cursor-pointer whitespace-nowrap shrink-0 ${
                active === t.id
                  ? 'border-instrument text-instrument'
                  : 'border-transparent text-ink-dim hover:text-ink'
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
        {activeTab.subtabs && (
          <nav className="max-w-6xl mx-auto px-6 flex gap-1 overflow-x-auto border-t border-hairline/60">
            {activeTab.subtabs.map((s) => (
              <button
                key={s.id}
                onClick={() => navigate(active, s.id)}
                className={`px-3 py-1.5 text-xs font-medium border-b-2 transition-colors cursor-pointer whitespace-nowrap shrink-0 ${
                  activeSub.id === s.id
                    ? 'border-instrument text-instrument'
                    : 'border-transparent text-ink-dim hover:text-ink'
                }`}
              >
                {s.label}
              </button>
            ))}
          </nav>
        )}
      </header>

      <main className="max-w-6xl mx-auto px-6 py-6">
        <ActiveView navigate={navigate} navContext={navContext} />
      </main>
    </div>
  )
}
