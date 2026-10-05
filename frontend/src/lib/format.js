// Formatage francais : espace pour les milliers, virgule decimale.
export const fmtInt = (n) => Math.round(n).toLocaleString('fr-FR')

export const fmtNum = (n, decimals = 1) =>
  Number(n).toLocaleString('fr-FR', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })

// epoch ms (tel que renvoye par pandas df.to_json) -> date/heure lisible.
export const fmtDate = (ms) => new Date(ms).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })

export const fmtPct = (x, decimals = 1) => `${(x * 100).toFixed(decimals).replace('.', ',')} %`
