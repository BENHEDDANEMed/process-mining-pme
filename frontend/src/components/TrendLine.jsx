import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

// Courbe simple (recharts LineChart) : seul composant a tracer une tendance
// continue plutot que des barres -- HBarChart/Histogram n'en ont pas besoin.
export function TrendLine({ data, xKey = 'x', yKey = 'y', xLabel, yLabel, color = '#3da9fc', valueFormatter = String }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 24, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#263252" />
        <XAxis
          dataKey={xKey}
          tick={{ fontSize: 11, fill: '#8b98b8' }}
          axisLine={{ stroke: '#263252' }}
          label={{ value: xLabel, position: 'insideBottom', offset: -18, fontSize: 12, fill: '#8b98b8' }}
        />
        <YAxis
          tick={{ fontSize: 12, fill: '#8b98b8' }}
          axisLine={{ stroke: '#263252' }}
          label={{ value: yLabel, angle: -90, position: 'insideLeft', fontSize: 12, fill: '#8b98b8' }}
        />
        <Tooltip
          formatter={(v) => valueFormatter(v)}
          contentStyle={{ fontSize: 13, borderRadius: 8, border: '1px solid #263252', background: '#121a30', color: '#e6ebf5' }}
          labelStyle={{ color: '#e6ebf5' }}
        />
        <Line type="monotone" dataKey={yKey} stroke={color} strokeWidth={2} dot={{ r: 3, fill: color }} />
      </LineChart>
    </ResponsiveContainer>
  )
}
