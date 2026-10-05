import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

// `bins` rows: { label, count }. Precomputed server-side (numpy.histogram).
export function Histogram({ bins, xLabel, yLabel = 'Nombre de cas', color = '#3da9fc' }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={bins} margin={{ top: 4, right: 16, bottom: 24, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#263252" />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 11, fill: '#8b98b8' }}
          axisLine={{ stroke: '#263252' }}
          label={{ value: xLabel, position: 'insideBottom', offset: -18, fontSize: 12, fill: '#8b98b8' }}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 12, fill: '#8b98b8' }}
          axisLine={{ stroke: '#263252' }}
          label={{ value: yLabel, angle: -90, position: 'insideLeft', fontSize: 12, fill: '#8b98b8' }}
        />
        <Tooltip
          contentStyle={{ fontSize: 13, borderRadius: 8, border: '1px solid #263252', background: '#121a30', color: '#e6ebf5' }}
          labelStyle={{ color: '#e6ebf5' }}
          cursor={{ fill: '#16213f' }}
        />
        <Bar dataKey="count" fill={color} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
