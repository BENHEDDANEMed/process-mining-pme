import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

// Multi-line y-axis tick: label may contain "\n" (e.g. "A →\nB") to avoid
// overlapping text for long two-part labels (bottleneck transitions).
function WrapTick({ x, y, payload }) {
  const lines = String(payload.value).split('\n')
  return (
    <text x={x} y={y} textAnchor="end" fontSize={12} fill="#8b98b8">
      {lines.map((line, i) => (
        <tspan key={i} x={x} dy={i === 0 ? -((lines.length - 1) * 6) : 12}>
          {line}
        </tspan>
      ))}
    </text>
  )
}

// Generic horizontal bar chart. `data` rows need { label, value }.
// ponytail: single reusable chart for health/activities/bottlenecks, no per-view chart code.
export function HBarChart({ data, height, color = '#3da9fc', colorOf, valueFormatter = String, domain, labelWidth = 220 }) {
  const rowHeight = 34
  return (
    <ResponsiveContainer width="100%" height={height ?? Math.max(160, data.length * rowHeight)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 48, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#263252" />
        <XAxis type="number" domain={domain} tick={{ fontSize: 12, fill: '#8b98b8' }} axisLine={{ stroke: '#263252' }} />
        <YAxis
          type="category"
          dataKey="label"
          width={labelWidth}
          tick={<WrapTick />}
          axisLine={{ stroke: '#263252' }}
          tickLine={false}
        />
        <Tooltip
          formatter={(v) => valueFormatter(v)}
          contentStyle={{ fontSize: 13, borderRadius: 8, border: '1px solid #263252', background: '#121a30', color: '#e6ebf5' }}
          labelStyle={{ color: '#e6ebf5' }}
          cursor={{ fill: '#16213f' }}
        />
        <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={22}>
          {data.map((row, i) => (
            <Cell key={i} fill={colorOf ? colorOf(row) : color} />
          ))}
          <LabelList dataKey="value" position="right" formatter={valueFormatter} style={{ fontSize: 12, fill: '#e6ebf5', fontFamily: 'var(--font-mono)' }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
