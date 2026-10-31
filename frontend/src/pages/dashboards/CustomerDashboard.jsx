import { CreditCard, Receipt, Repeat, Store, UserRound } from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  Empty,
  FREQUENCY_LABEL,
  Kpi,
  ListRow,
  Panel,
  QuickActions,
  StatusBadge,
  daysFromToday,
  formatDate,
  money,
  relativeDays,
} from '../../components/ui'
import './dashboards.css'

function termProgress(start, end) {
  const total = daysFromToday(end) - daysFromToday(start)
  if (!start || !end || total <= 0) return 0
  const elapsed = -daysFromToday(start)
  return Math.min(100, Math.max(0, (elapsed / total) * 100))
}

function Feature({ label, allowed }) {
  return (
    <li>
      <span>{label}</span>
      <b className={allowed ? 'yes' : 'no'}>{allowed ? 'Allowed' : 'Not on this plan'}</b>
    </li>
  )
}

export default function CustomerDashboard({ data }) {
  const { stats, active_subscription: subscription } = data
  const plan = subscription?.plan_detail
  const renewSoon = data.days_to_renewal !== null && data.days_to_renewal <= 30

  return (
    <>
      <QuickActions
        actions={[
          { to: '/browse-plans', label: 'Browse plans', icon: Store },
          { to: '/subscriptions', label: 'View my subscriptions', icon: Repeat },
          { to: '/invoices', label: 'View invoices', icon: Receipt },
          { to: '/payments', label: 'View payment history', icon: CreditCard },
          { to: '/account', label: 'Manage account', icon: UserRound },
        ]}
      />

      <div className="kpi-grid">
        <Kpi label="Active subscriptions" value={stats.active_subscriptions} tone="sage" />
        <Kpi label="Total invoices" value={stats.total_invoices} hint="Excludes drafts and cancelled" />
        <Kpi label="Paid invoices" value={stats.paid_invoices} />
        <Kpi
          label="Pending payments"
          value={money(stats.pending_payments.amount)}
          hint={`${stats.pending_payments.count} open invoice${stats.pending_payments.count === 1 ? '' : 's'}`}
          tone="amber"
        />
        <Kpi
          label="Overdue"
          value={money(stats.overdue_payments.amount)}
          hint={stats.overdue_payments.count ? `${stats.overdue_payments.count} past their due date` : 'Nothing overdue'}
          tone={stats.overdue_payments.count ? 'clay' : 'pine'}
        />
      </div>

      <div className="panel-grid wide-left">
        {subscription ? (
          <Panel title="My subscription" action={<Link to={`/subscriptions/${subscription.id}`}>Manage</Link>}>
            <div className="plan-card-main">
              <div className="plan-card-head">
                <div>
                  <span className="product-tag">{plan.product_name}</span>
                  <h2>{plan.name}</h2>
                  <p className="list-meta">
                    <span className="mono">{subscription.number}</span> · <StatusBadge status={subscription.status} />
                  </p>
                </div>
                <div className="plan-card-price">
                  {money(plan.price)}
                  <small>per {FREQUENCY_LABEL[plan.billing_frequency]}</small>
                </div>
              </div>

              <div className="detail-grid">
                <div className="detail-item">
                  <span>Next billing</span>
                  <strong>{formatDate(data.next_billing_date)}</strong>
                  <small className="list-meta">{relativeDays(data.next_billing_date)}</small>
                </div>
                <div className="detail-item">
                  <span>Next charge</span>
                  <strong className="num">{money(data.next_billing_amount, 2)}</strong>
                  <small className="list-meta">Before tax and discounts</small>
                </div>
                <div className="detail-item">
                  <span>Started</span>
                  <strong>{formatDate(subscription.start_date)}</strong>
                </div>
                <div className="detail-item">
                  <span>Payment terms</span>
                  <strong>{subscription.payment_terms.replace('_', ' ')}</strong>
                </div>
              </div>

              {subscription.expiry_date && (
                <div className="term-progress">
                  <div className="term-progress-top">
                    <span>Term ends {formatDate(subscription.expiry_date)}</span>
                    <span>{data.days_to_renewal >= 0 ? `${data.days_to_renewal} days left` : 'Expired'}</span>
                  </div>
                  <div className={`term-bar ${renewSoon ? 'soon' : ''}`}>
                    <i style={{ width: `${termProgress(subscription.start_date, subscription.expiry_date)}%` }} />
                  </div>
                </div>
              )}
            </div>
          </Panel>
        ) : (
          <Panel title="My subscription">
            <Empty title="No active subscription">
              <Link to="/browse-plans">Browse plans</Link> to get started.
            </Empty>
          </Panel>
        )}

        <Panel title="What your plan allows">
          {plan ? (
            <ul className="feature-list">
              <li>
                <span>Billing</span>
                <b>{plan.billing_frequency}</b>
              </li>
              <Feature label="Pause billing" allowed={plan.allow_pause} />
              <Feature label="Close early" allowed={plan.allow_early_closure} />
              <Feature label="Renew at term end" allowed={plan.allow_renewal} />
              <li>
                <span>Closes by itself</span>
                <b>{plan.auto_close_enabled ? 'At term end' : 'No'}</b>
              </li>
            </ul>
          ) : (
            <Empty>Subscribe to a plan to see what it allows.</Empty>
          )}
        </Panel>
      </div>

      <div className="panel-grid">
        <Panel title="Recent invoices" action={<Link to="/invoices">View all</Link>}>
          {data.recent_invoices.length === 0 && <Empty title="No invoices yet" />}
          {data.recent_invoices.map((i) => (
            <ListRow
              key={i.id}
              to={`/invoices/${i.id}`}
              title={<span className="mono">{i.number}</span>}
              meta={`Due ${formatDate(i.due_date)}`}
              aside={money(i.amount, 2)}
              asideMeta={
                i.status === 'confirmed' ? (
                  <span className="pay-now">{i.is_overdue ? 'Overdue, pay now' : 'Pay now'}</span>
                ) : (
                  <StatusBadge status={i.status} />
                )
              }
            />
          ))}
        </Panel>
        <Panel title="Payment history" action={<Link to="/payments">View all</Link>}>
          {data.payment_history.length === 0 && <Empty title="No payments yet" />}
          {data.payment_history.map((p) => (
            <ListRow
              key={p.id}
              to={`/invoices/${p.invoice}`}
              title={money(p.amount, 2)}
              meta={
                <>
                  <span className="mono">{p.invoice_number}</span> · {p.method.replace('_', ' ')}
                </>
              }
              aside={formatDate(p.paid_on)}
            />
          ))}
        </Panel>
      </div>

      <Panel title="Available plans" subtitle="Open for new subscriptions today" action={<Link to="/browse-plans">Browse all</Link>}>
        {data.available_plans.length === 0 && <Empty title="No plans available right now" />}
        <div className="mini-plans">
          {data.available_plans.map((p) => (
            <div key={p.id} className="mini-plan">
              <span className="product-tag">{p.product}</span>
              <strong>{p.name}</strong>
              <span>
                {money(p.price)} per {FREQUENCY_LABEL[p.billing_frequency]} · min {p.min_quantity}
              </span>
            </div>
          ))}
        </div>
      </Panel>
    </>
  )
}
