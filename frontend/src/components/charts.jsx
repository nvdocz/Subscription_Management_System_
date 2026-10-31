import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { compactMoney, money } from './ui'

const CHART_COLORS = {
  pine: '#12493b',
  amber: '#d9891a',
  clay: '#c0603f',
  sage: '#8fb39c',
  slate: '#94a3b8',
  info: '#2c6a94',
  stone: '#cfc7b4',
  grid: '#e2dccd',
  text: '#55625b',
}

const STATUS_COLORS = {
  draft: CHART_COLORS.stone,
  quotation: CHART_COLORS.sage,
  confirmed: CHART_COLORS.info,
  active: CHART_COLORS.pine,
  paused: CHART_COLORS.amber,
  closed: CHART_COLORS.clay,
}

const INVOICE_COLORS = {
  paid: CHART_COLORS.pine,
  confirmed: CHART_COLORS.amber,
  overdue: CHART_COLORS.clay,
  draft: CHART_COLORS.stone,
  cancelled: CHART_COLORS.slate,
}

const tooltipStyle = {
  background: '#fffefa',
  border: '1px solid #e2dccd',
  borderRadius: 8,
  color: '#14211c',
  fontSize: 12.5,
  boxShadow: '0 10px 30px -12px rgba(20, 33, 28, 0.25)',
  padding: '8px 12px',
}

const tick = { fill: CHART_COLORS.text, fontSize: 11.5 }
const axisLine = { stroke: CHART_COLORS.grid }
const num = (v) => Number(v ?? 0)

function axisMoney(value) {
  const n = Math.abs(Number(value))
  const sign = value < 0 ? '-' : ''
  if (n >= 10000000) return `${sign}${(n / 10000000).toFixed(1)}Cr`
  if (n >= 100000) return `${sign}${(n / 100000).toFixed(1)}L`
  if (n >= 1000) return `${sign}${Math.round(n / 1000)}k`
  return `${value}`
}

function ChartBox({ height, children }) {
  return (
    <div className="chart-box" style={{ height }}>
      <ResponsiveContainer>{children}</ResponsiveContainer>
    </div>
  )
}

export function RevenueChart({ data, height = 260 }) {
  const rows = data.map((d) => ({ ...d, revenue: num(d.revenue) }))
  return (
    <ChartBox height={height}>
      <AreaChart data={rows} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART_COLORS.pine} stopOpacity={0.22} />
            <stop offset="100%" stopColor={CHART_COLORS.pine} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey="label" tick={tick} axisLine={axisLine} tickLine={false} interval="preserveStartEnd" />
        <YAxis tick={tick} axisLine={false} tickLine={false} width={46} tickFormatter={axisMoney} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v) => [money(v), 'Collected']} cursor={{ stroke: CHART_COLORS.stone }} />
        <Area
          type="monotone"
          dataKey="revenue"
          stroke={CHART_COLORS.pine}
          strokeWidth={2}
          fill="url(#revenueFill)"
          dot={{ r: 2.5, fill: CHART_COLORS.pine, strokeWidth: 0 }}
          isAnimationActive={false}
        />
      </AreaChart>
    </ChartBox>
  )
}

export function GrowthChart({ data, height = 260 }) {
  return (
    <ChartBox height={height}>
      <ComposedChart data={data} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey="label" tick={tick} axisLine={axisLine} tickLine={false} interval="preserveStartEnd" />
        <YAxis tick={tick} axisLine={false} tickLine={false} width={32} allowDecimals={false} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(226, 220, 205, 0.4)' }} />
        <Legend wrapperStyle={{ fontSize: 12, color: CHART_COLORS.text }} iconType="circle" iconSize={8} />
        <Bar dataKey="new" name="New this month" fill={CHART_COLORS.sage} radius={[3, 3, 0, 0]} barSize={20} isAnimationActive={false} />
        <Line
          type="monotone"
          dataKey="total"
          name="Total subscriptions"
          stroke={CHART_COLORS.pine}
          strokeWidth={2}
          dot={{ r: 2.5, fill: CHART_COLORS.pine, strokeWidth: 0 }}
          isAnimationActive={false}
        />
      </ComposedChart>
    </ChartBox>
  )
}

export function StatusDonut({ data, height = 260 }) {
  const total = data.reduce((sum, d) => sum + d.count, 0)
  const visible = data.filter((d) => d.count > 0)
  if (total === 0) {
    return (
      <div className="chart-box" style={{ height }}>
        <p className="empty">No subscriptions yet.</p>
      </div>
    )
  }
  return (
    <div className="donut-wrap" style={{ height }}>
      <div className="donut-chart">
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={visible}
              dataKey="count"
              nameKey="label"
              innerRadius="62%"
              outerRadius="92%"
              paddingAngle={2}
              stroke="#fffefa"
              strokeWidth={2}
              isAnimationActive={false}
            >
              {visible.map((d) => (
                <Cell key={d.status} fill={STATUS_COLORS[d.status] ?? CHART_COLORS.slate} />
              ))}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
        <div className="donut-center">
          <strong>{total}</strong>
          <span>total</span>
        </div>
      </div>
      <ul className="legend-list">
        {data.map((d) => (
          <li key={d.status}>
            <i style={{ background: STATUS_COLORS[d.status] ?? CHART_COLORS.slate }} />
            <span>{d.label}</span>
            <b>{d.count}</b>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function MrrMovementChart({ data, height = 260 }) {
  const rows = data.map((d) => ({ ...d, new: num(d.new), churned: num(d.churned), mrr: num(d.mrr) }))
  return (
    <ChartBox height={height}>
      <ComposedChart data={rows} stackOffset="sign" margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey="label" tick={tick} axisLine={axisLine} tickLine={false} interval="preserveStartEnd" />
        <YAxis yAxisId="move" tick={tick} axisLine={false} tickLine={false} width={46} tickFormatter={axisMoney} />
        <YAxis yAxisId="mrr" orientation="right" tick={tick} axisLine={false} tickLine={false} width={46} tickFormatter={axisMoney} />
        <ReferenceLine yAxisId="move" y={0} stroke={CHART_COLORS.stone} />
        <Tooltip
          contentStyle={tooltipStyle}
          cursor={{ fill: 'rgba(226, 220, 205, 0.4)' }}
          formatter={(v, name) => [money(Math.abs(v)), name]}
        />
        <Legend wrapperStyle={{ fontSize: 12, color: CHART_COLORS.text }} iconType="circle" iconSize={8} />
        <Bar yAxisId="move" dataKey="new" name="New MRR" stackId="m" fill={CHART_COLORS.sage} radius={[3, 3, 0, 0]} barSize={20} isAnimationActive={false} />
        <Bar yAxisId="move" dataKey="churned" name="Churned MRR" stackId="m" fill={CHART_COLORS.clay} radius={[0, 0, 3, 3]} barSize={20} isAnimationActive={false} />
        <Line
          yAxisId="mrr"
          type="monotone"
          dataKey="mrr"
          name="MRR"
          stroke={CHART_COLORS.amber}
          strokeWidth={2.2}
          dot={{ r: 2.5, fill: CHART_COLORS.amber, strokeWidth: 0 }}
          isAnimationActive={false}
        />
      </ComposedChart>
    </ChartBox>
  )
}

export function PaymentMethodBars({ data, height }) {
  const rows = data.map((d) => ({ ...d, amount: num(d.amount) }))
  if (rows.length === 0) {
    return <p className="empty">No payments recorded yet.</p>
  }
  const max = Math.max(...rows.map((r) => r.amount)) || 1
  const total = rows.reduce((sum, r) => sum + r.amount, 0) || 1
  return (
    <ul className="bar-rows" style={height ? { minHeight: height } : undefined}>
      {rows.map((r, i) => (
        <li key={r.method}>
          <div className="bar-row-head">
            <span>{r.label}</span>
            <b>{compactMoney(r.amount)}</b>
          </div>
          <div className="bar-track">
            <i style={{ width: `${(r.amount / max) * 100}%`, background: [CHART_COLORS.pine, CHART_COLORS.amber, CHART_COLORS.sage, CHART_COLORS.clay, CHART_COLORS.slate][i % 5] }} />
          </div>
          <small>
            {r.count} {r.count === 1 ? 'payment' : 'payments'} · {Math.round((r.amount / total) * 100)}%
          </small>
        </li>
      ))}
    </ul>
  )
}

export function InvoiceBreakdownBar({ data }) {
  const rows = data.filter((d) => d.count > 0)
  const total = rows.reduce((sum, d) => sum + d.count, 0)
  if (total === 0) {
    return <p className="empty">No invoices yet.</p>
  }
  return (
    <div className="stack-bar-wrap">
      <div className="stack-bar" role="img" aria-label="Invoice status split">
        {rows.map((d) => (
          <i
            key={d.status}
            title={`${d.label}: ${d.count}`}
            style={{ width: `${(d.count / total) * 100}%`, background: INVOICE_COLORS[d.status] ?? CHART_COLORS.slate }}
          />
        ))}
      </div>
      <ul className="legend-grid">
        {data.map((d) => (
          <li key={d.status}>
            <i style={{ background: INVOICE_COLORS[d.status] ?? CHART_COLORS.slate }} />
            <span>{d.label}</span>
            <b>{d.count}</b>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function AgingBars({ data, height = 220 }) {
  const rows = data.map((d) => ({ ...d, amount: num(d.amount) }))
  return (
    <ChartBox height={height}>
      <BarChart data={rows} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey="label" tick={tick} axisLine={axisLine} tickLine={false} />
        <YAxis tick={tick} axisLine={false} tickLine={false} width={46} tickFormatter={axisMoney} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v) => [money(v), 'Outstanding']} cursor={{ fill: 'rgba(226, 220, 205, 0.4)' }} />
        <Bar dataKey="amount" radius={[3, 3, 0, 0]} barSize={34} isAnimationActive={false}>
          {rows.map((r, i) => (
            <Cell key={r.label} fill={[CHART_COLORS.sage, CHART_COLORS.amber, CHART_COLORS.clay, '#8c3a24'][i] ?? CHART_COLORS.clay} />
          ))}
        </Bar>
      </BarChart>
    </ChartBox>
  )
}
