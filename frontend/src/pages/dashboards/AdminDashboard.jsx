import { ChartColumn, FileText, Layers, Package, UserPlus } from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  GrowthChart,
  InvoiceBreakdownBar,
  MrrMovementChart,
  PaymentMethodBars,
  RevenueChart,
  StatusDonut,
} from '../../components/charts'
import { Empty, Kpi, ListRow, Panel, QuickActions, StatusBadge, compactMoney, formatDate, money } from '../../components/ui'
import './dashboards.css'

const num = (v) => Number(v ?? 0)

function trend(series, key) {
  if (series.length < 2) return null
  const last = num(series.at(-1)[key])
  const prev = num(series.at(-2)[key])
  if (!prev) return null
  const pct = ((last - prev) / Math.abs(prev)) * 100
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}% vs last month`
}

export default function AdminDashboard({ data }) {
  const { stats } = data
  const collected = num(stats.collection.collected)
  const billed = num(stats.collection.billed)
  const collectionRate = billed > 0 ? `${Math.round((collected / billed) * 100)}%` : '—'

  return (
    <>
      <QuickActions
        actions={[
          { to: '/users/new?role=staff', label: 'Add staff', icon: UserPlus },
          { to: '/products/new', label: 'Add product', icon: Package },
          { to: '/plans/new', label: 'Create subscription plan', icon: Layers },
          { to: '/quotations/new', label: 'Create quotation', icon: FileText },
          { to: '/reports', label: 'View reports', icon: ChartColumn },
        ]}
      />

      <div className="kpi-grid">
        <Kpi label="Total customers" value={stats.total_customers} hint={`${stats.new_customers_30d} joined in 30 days`} />
        <Kpi label="Total staff" value={stats.total_staff} hint="Internal team accounts" />
        <Kpi label="Total products" value={stats.total_products} hint="Active catalogue" />
        <Kpi label="Active subscriptions" value={stats.active_subscriptions} hint={`${stats.churned_30d} closed in 30 days`} tone="sage" />
        <Kpi
          label="Monthly recurring revenue"
          value={money(stats.monthly_recurring_revenue)}
          hint={trend(data.mrr_movement, 'mrr') ?? 'Active subscriptions only'}
          spark={data.mrr_movement.map((r) => num(r.mrr))}
        />
        <Kpi
          label="Total revenue"
          value={money(stats.total_revenue)}
          hint="All payments received"
          spark={data.revenue_by_month.map((r) => num(r.revenue))}
        />
        <Kpi
          label="Outstanding invoices"
          value={stats.outstanding_invoices.count}
          hint={`${money(stats.outstanding_invoices.amount)} to collect`}
          tone="amber"
        />
        <Kpi
          label="Overdue invoices"
          value={stats.overdue_invoices.count}
          hint={`${money(stats.overdue_invoices.amount)} past due`}
          tone="clay"
        />
      </div>

      <div className="figure-strip">
        <div className="figure">
          <span>Annual run rate</span>
          <strong>{compactMoney(stats.annual_recurring_revenue)}</strong>
          <small>MRR × 12</small>
        </div>
        <div className="figure">
          <span>Collected this month</span>
          <strong>{compactMoney(stats.revenue_this_month)}</strong>
          <small>Payments dated this month</small>
        </div>
        <div className="figure">
          <span>New customers</span>
          <strong>{stats.new_customers_30d}</strong>
          <small>Last 30 days</small>
        </div>
        <div className="figure">
          <span>Churned</span>
          <strong>{stats.churned_30d}</strong>
          <small>Closed in 30 days</small>
        </div>
        <div className="figure">
          <span>Collection rate</span>
          <strong>{collectionRate}</strong>
          <small>
            {compactMoney(collected)} of {compactMoney(billed)} billed
          </small>
        </div>
        <div className="figure">
          <span>Billing forecast</span>
          <strong>{compactMoney(stats.billing_forecast_30d.amount)}</strong>
          <small>{stats.billing_forecast_30d.count} subscriptions in 30 days</small>
        </div>
      </div>

      <div className="panel-grid wide-left">
        <Panel title="Revenue analytics" subtitle="Payments received, last 6 months">
          <RevenueChart data={data.revenue_by_month} />
        </Panel>
        <Panel title="Subscription status" subtitle="Every subscription on the books">
          <StatusDonut data={data.status_breakdown} />
        </Panel>
      </div>

      <div className="panel-grid">
        <Panel title="MRR movement" subtitle="New and churned recurring revenue, with running MRR">
          <MrrMovementChart data={data.mrr_movement} />
        </Panel>
        <Panel title="Subscription growth" subtitle="Subscriptions started per month">
          <GrowthChart data={data.subscription_growth} />
        </Panel>
      </div>

      <div className="panel-grid">
        <Panel title="Invoice status" subtitle="Share of invoices by where they stand">
          <InvoiceBreakdownBar data={data.invoice_breakdown} />
        </Panel>
        <Panel title="How customers pay" subtitle="Payment methods by value">
          <PaymentMethodBars data={data.payment_methods} />
        </Panel>
      </div>

      <div className="panel-grid">
        <Panel title="Overdue, worth a chase" action={<Link to="/invoices?overdue=1">All overdue</Link>}>
          {data.overdue_invoices.length === 0 && <Empty title="Nothing overdue">Every confirmed invoice is within its terms.</Empty>}
          {data.overdue_invoices.map((i) => (
            <ListRow
              key={i.id}
              to={`/invoices/${i.id}`}
              title={<span className="mono">{i.number}</span>}
              meta={`${i.customer} · due ${formatDate(i.due_date)}`}
              aside={money(i.balance, 2)}
              asideMeta={<span className="chase-days">{i.days_overdue}d overdue</span>}
            />
          ))}
        </Panel>
        <Panel title="Recent customer registrations" action={<Link to="/users">View all</Link>}>
          {data.recent_customers.length === 0 && <Empty title="No customers yet" />}
          {data.recent_customers.map((c) => (
            <ListRow key={c.id} title={c.username} meta={c.email} aside={formatDate(c.date_joined)} />
          ))}
        </Panel>
      </div>

      <div className="panel-grid">
        <Panel title="Recent subscriptions" action={<Link to="/subscriptions">View all</Link>}>
          {data.recent_subscriptions.length === 0 && <Empty title="No subscriptions yet" />}
          {data.recent_subscriptions.map((s) => (
            <ListRow
              key={s.id}
              to={`/subscriptions/${s.id}`}
              title={
                <>
                  <span className="mono">{s.number}</span> · {s.customer_detail.username}
                </>
              }
              meta={`${s.plan_detail.name} · ${s.plan_detail.product_name}`}
              aside={<StatusBadge status={s.status} />}
              asideMeta={`Since ${formatDate(s.start_date)}`}
            />
          ))}
        </Panel>
        <Panel title="Recent invoices" action={<Link to="/invoices">View all</Link>}>
          {data.recent_invoices.length === 0 && <Empty title="No invoices yet" />}
          {data.recent_invoices.map((i) => (
            <ListRow
              key={i.id}
              to={`/invoices/${i.id}`}
              title={
                <>
                  <span className="mono">{i.number}</span> · {i.customer_detail.username}
                </>
              }
              meta={`Due ${formatDate(i.due_date)}`}
              aside={money(i.amount, 2)}
              asideMeta={<StatusBadge status={i.is_overdue ? 'overdue' : i.status} />}
            />
          ))}
        </Panel>
      </div>

      <Panel title="Recent payments" action={<Link to="/payments">View all</Link>}>
        {data.recent_payments.length === 0 && <Empty title="No payments recorded yet" />}
        {data.recent_payments.map((p) => (
          <ListRow
            key={p.id}
            to={`/invoices/${p.invoice}`}
            title={`${p.customer_name} paid ${money(p.amount, 2)}`}
            meta={
              <>
                <span className="mono">{p.invoice_number}</span> · {p.method.replace('_', ' ')}
              </>
            }
            aside={formatDate(p.paid_on)}
          />
        ))}
      </Panel>
    </>
  )
}
