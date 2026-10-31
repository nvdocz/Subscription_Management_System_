import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Download, Printer, RotateCcw } from 'lucide-react'
import api from '../api/client'
import { getReports } from '../api/dashboard'
import {
  AgingBars,
  GrowthChart,
  InvoiceBreakdownBar,
  MrrMovementChart,
  PaymentMethodBars,
  RevenueChart,
  StatusDonut,
} from '../components/charts'
import { Empty, PageHeader, PageSkeleton, Panel, compactMoney, formatDate, money } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import './dashboards/dashboards.css'
import './Reports.css'

const EMPTY_FILTERS = { from: '', to: '', plan: '' }
const num = (v) => Number(v ?? 0)

function downloadOverdueCsv(rows) {
  const header = ['Invoice', 'Customer', 'Due date', 'Days overdue', 'Balance']
  const lines = rows.map((r) => [r.number, r.customer, r.due_date, r.days_overdue, num(r.balance).toFixed(2)])
  const csv = [header, ...lines].map((cols) => cols.map((c) => `"${String(c).replaceAll('"', '""')}"`).join(',')).join('\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `overdue-invoices-${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

export default function ReportsPage() {
  const { user } = useAuth()
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [result, setResult] = useState(null)
  const [planOptions, setPlanOptions] = useState([])
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const key = JSON.stringify(filters)
  const data = result?.report ?? null
  const refreshing = Boolean(result) && result.key !== key

  // Admins can read /plans/; staff cannot, so their options come from the unfiltered report.
  useEffect(() => {
    if (user.role !== 'admin') return
    api
      .get('/plans/')
      .then((res) => setPlanOptions(res.data.map((p) => ({ id: p.id, name: p.name }))))
      .catch(() => {})
  }, [user.role])

  useEffect(() => {
    let active = true
    getReports(filters)
      .then((report) => {
        if (!active) return
        setError(false)
        setResult({ key, report })
        if (user.role !== 'admin' && !filters.plan) {
          setPlanOptions(report.plans.map((p) => ({ id: p.plan_id, name: p.plan })))
        }
      })
      .catch(() => active && setError(true))
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt, user.role])

  const set = (field) => (e) => setFilters((prev) => ({ ...prev, [field]: e.target.value }))
  const filtered = Boolean(filters.from || filters.to || filters.plan)

  if (error && !data) {
    return (
      <div>
        <PageHeader eyebrow="Finance" title="Reports" />
        <div className="error-panel">
          <p className="form-error">The report could not be loaded.</p>
          <button type="button" className="btn-secondary" onClick={() => setAttempt((n) => n + 1)}>
            Try again
          </button>
        </div>
      </div>
    )
  }

  const summary = data?.summary
  const agingTotal = data ? data.invoice_aging.reduce((sum, row) => sum + num(row.amount), 0) : 0
  const planTotal = data ? data.plans.reduce((sum, row) => sum + num(row.mrr), 0) : 0

  return (
    <div className="report-page">
      <PageHeader
        eyebrow="Finance"
        title="Reports"
        subtitle="Active subscriptions, revenue, payments and overdue invoices in one place."
        actions={
          <>
            <button type="button" className="btn-secondary" onClick={() => window.print()}>
              <Printer size={15} /> Print
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={!data || data.overdue_invoices.length === 0}
              onClick={() => downloadOverdueCsv(data.overdue_invoices)}
            >
              <Download size={15} /> Overdue CSV
            </button>
          </>
        }
      />

      <div className="report-filters">
        <label>
          <span>From</span>
          <input type="date" value={filters.from} max={filters.to || undefined} onChange={set('from')} />
        </label>
        <label>
          <span>To</span>
          <input type="date" value={filters.to} min={filters.from || undefined} onChange={set('to')} />
        </label>
        <label>
          <span>Plan</span>
          <select value={filters.plan} onChange={set('plan')}>
            <option value="">All plans</option>
            {planOptions.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        {filtered && (
          <button type="button" className="btn-ghost" onClick={() => setFilters(EMPTY_FILTERS)}>
            <RotateCcw size={14} /> Clear filters
          </button>
        )}
        <span className="report-scope">
          {filtered
            ? `Revenue, invoicing and payments are filtered${filters.from ? ` from ${formatDate(filters.from)}` : ''}${filters.to ? ` to ${formatDate(filters.to)}` : ''}${filters.plan ? ' for the selected plan' : ''}.`
            : 'Showing all time. Pick dates or a plan to narrow it down.'}
        </span>
      </div>

      {!data ? (
        <PageSkeleton />
      ) : (
        <div className={refreshing ? 'is-refreshing' : ''}>
          <div className="figure-strip report-strip">
            <div className="figure">
              <span>Active subscriptions</span>
              <strong>{summary.active_subscriptions}</strong>
              <small>of {summary.total_subscriptions} in total</small>
            </div>
            <div className="figure">
              <span>MRR</span>
              <strong>{compactMoney(summary.mrr)}</strong>
              <small>ARR {compactMoney(summary.arr)}</small>
            </div>
            <div className="figure">
              <span>Revenue</span>
              <strong>{compactMoney(summary.revenue)}</strong>
              <small>
                {summary.payments_count} payment{summary.payments_count === 1 ? '' : 's'}
              </small>
            </div>
            <div className="figure">
              <span>Invoiced</span>
              <strong>{compactMoney(summary.invoiced)}</strong>
              <small>Confirmed and paid</small>
            </div>
            <div className="figure">
              <span>Collection rate</span>
              <strong>{summary.collection_rate === null ? '—' : `${summary.collection_rate}%`}</strong>
              <small>Revenue against invoiced</small>
            </div>
            <div className="figure">
              <span>Outstanding</span>
              <strong>{compactMoney(summary.outstanding.amount)}</strong>
              <small>{summary.outstanding.count} invoices open</small>
            </div>
            <div className="figure danger">
              <span>Overdue</span>
              <strong>{compactMoney(summary.overdue.amount)}</strong>
              <small>{summary.overdue.count} past their due date</small>
            </div>
            <div className="figure">
              <span>New vs closed</span>
              <strong>
                {summary.new_subscriptions} <em>/</em> {summary.closed_subscriptions}
              </strong>
              <small>Subscriptions in this period</small>
            </div>
          </div>

          <div className="panel-grid">
            <Panel title="Revenue" subtitle="Payments received, last 12 months">
              <RevenueChart data={data.revenue_by_month} />
            </Panel>
            <Panel title="MRR movement" subtitle="New and churned recurring revenue, last 12 months">
              <MrrMovementChart data={data.mrr_movement} />
            </Panel>
          </div>

          <div className="panel-grid">
            <Panel title="Subscription growth" subtitle="Started per month and running total">
              <GrowthChart data={data.subscription_growth} />
            </Panel>
            <Panel title="Subscription status" subtitle="Where every subscription stands">
              <StatusDonut data={data.status_breakdown} />
            </Panel>
          </div>

          <div className="panel-grid">
            <Panel title="Invoice status" subtitle="Share of invoices by outcome">
              <InvoiceBreakdownBar data={data.invoice_breakdown} />
            </Panel>
            <Panel title="Payment methods" subtitle={filtered ? 'Within the selected filters' : 'All payments'}>
              <PaymentMethodBars data={data.payment_methods} />
            </Panel>
          </div>

          <div className="panel-grid">
            <Panel title="Revenue by plan" subtitle="Active subscriptions and their monthly recurring revenue" flush>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Plan</th>
                    <th>Product</th>
                    <th className="num">Active</th>
                    <th className="num">MRR</th>
                    <th className="num">Share</th>
                  </tr>
                </thead>
                <tbody>
                  {data.plans.map((p) => (
                    <tr key={p.plan_id}>
                      <td className="strong">{p.plan}</td>
                      <td>{p.product}</td>
                      <td className="num">{p.active_subscriptions}</td>
                      <td className="num">{money(p.mrr)}</td>
                      <td className="num">{planTotal ? `${Math.round((num(p.mrr) / planTotal) * 100)}%` : '—'}</td>
                    </tr>
                  ))}
                  {data.plans.length === 0 && (
                    <tr>
                      <td colSpan={5} className="empty-cell">
                        No plans to report on.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </Panel>

            <Panel title="Invoice aging" subtitle={`Outstanding ${money(agingTotal)} across all open invoices`}>
              <AgingBars data={data.invoice_aging} height={190} />
              <table className="data-table aging-table">
                <tbody>
                  {data.invoice_aging.map((row) => (
                    <tr key={row.label}>
                      <td>{row.label}</td>
                      <td className="num strong">{money(row.amount, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
          </div>

          <Panel
            title="Overdue invoices"
            subtitle="Oldest first. Chase these before they become lost revenue."
            action={<Link to="/invoices?overdue=1">Open in invoices</Link>}
            flush
          >
            <table className="data-table">
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Customer</th>
                  <th>Due</th>
                  <th className="num">Days overdue</th>
                  <th className="num">Balance</th>
                </tr>
              </thead>
              <tbody>
                {data.overdue_invoices.map((i) => (
                  <tr key={i.id}>
                    <td>
                      <Link className="doc" to={`/invoices/${i.id}`}>
                        {i.number}
                      </Link>
                    </td>
                    <td className="strong">{i.customer}</td>
                    <td>{formatDate(i.due_date)}</td>
                    <td className="num">
                      <span className="chase-days">{i.days_overdue}d</span>
                    </td>
                    <td className="num strong">{money(i.balance, 2)}</td>
                  </tr>
                ))}
                {data.overdue_invoices.length === 0 && (
                  <tr>
                    <td colSpan={5} className="empty-cell">
                      <Empty title="Nothing overdue">Every confirmed invoice is within its payment terms.</Empty>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </Panel>

          <p className="report-footnote">
            Forecast: {data.billing_forecast_30d.count} subscriptions bill in the next 30 days for about{' '}
            {money(data.billing_forecast_30d.amount)} before tax and discounts. MRR and the status charts always show today&apos;s book.
          </p>
        </div>
      )}
    </div>
  )
}
