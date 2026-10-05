async function get(path) {
  const res = await fetch(`/api${path}`)
  if (!res.ok) throw new Error(`${path} -> ${res.status}`)
  return res.json()
}

export const api = {
  overview: () => get('/overview'),
  process: () => get('/process'),
  conformance: () => get('/conformance'),
  recommendations: () => get('/recommendations'),
  cases: (q = '') => get(`/prediction/cases?q=${encodeURIComponent(q)}`),
  caseSteps: (caseId) => get(`/prediction/${encodeURIComponent(caseId)}`),
  prediction: (caseId, step) => get(`/prediction/${encodeURIComponent(caseId)}/${step}`),
  variants: (topN = 20) => get(`/variants?top_n=${topN}`),
  caseList: (params = {}) => get(`/cases?${new URLSearchParams(params)}`),
  caseDetail: (caseId) => get(`/cases/${encodeURIComponent(caseId)}`),
  explain: (caseId, step) => get(`/prediction/${encodeURIComponent(caseId)}/${step}/explain`),
  rootCause: (topN = 8) => get(`/root-cause?top_n=${topN}`),
  monitoringOverview: () => get('/monitoring/overview'),
  monitoringHighRisk: (params = {}) => get(`/monitoring/high-risk?${new URLSearchParams(params)}`),
  monitoringHistory: (caseId) => get(`/monitoring/case/${encodeURIComponent(caseId)}/history`),
}
