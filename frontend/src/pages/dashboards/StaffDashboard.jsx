import { FileText, HandCoins, Receipt, Repeat, UserPlus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Empty, Kpi, ListRow, Panel, QuickActions, StatusBadge, formatDate, money, relativeDays } from '../../components/ui'
import './dashboards.css'

export default function StaffDashboard({ data }) {
  const { stats } = data

  return (
    <>
      <QuickActions
        actions={[
          { to: '/users/new', label: 'Add customer', icon: UserPlus },
          { to: '/quotations/new', label: 'Create quotation', icon: FileText },
          { to: '/subscriptions', label: 'View subscriptions', icon: Repeat },
          { to: '/invoices', label: 'Manage invoices', icon: Receipt },
          { to: '/payments/new', label: 'Record payment', icon: HandCoins },
        ]}
      />

      <div className="kpi-grid">
        <Kpi label="Assigned customers" value={stats.assigned_customers} hint="Customers you have quoted" />
        <Kpi label="Total quotations" value={stats.total_quotations} hint="Across the team" />
        <Kpi label="Pending quotations" value={stats.pending_quotations} hint="Draft or sent" tone="amber" />
        <Kpi label="Active subscriptions" value={stats.active_subscriptions} tone="sage" />
        <Kpi
          label="Pending invoices"
          value={stats.pending_invoices.count}
          hint={`${money(stats.pending_invoices.amount)} awaiting payment`}
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
          <span>Draft invoices</span>
          <strong>{stats.draft_invoices}</strong>
          <small>
            <Link to="/invoices?status=draft">Review and confirm</Link>
          </small>
        </div>
        <div className="figure">
          <span>Due for billing</span>
          <strong>{stats.due_for_billing}</strong>
          <small>
            <Link to="/billing-run">{stats.due_for_billing > 0 ? 'Open the billing run' : 'Billing run is up to date'}</Link>
          </small>
        </div>
      </div>

      <div className="panel-grid">
        <Panel title="Quotations awaiting action" action={<Link to="/quotations">View all</Link>}>
          {data.quotations_awaiting_action.length === 0 && <Empty title="All caught up">No draft or sent quotations are waiting.</Empty>}
          {data.quotations_awaiting_action.map((q) => (
            <ListRow
              key={q.id}
              to="/quotations"
              title={`#${q.id} · ${q.customer}`}
              meta={`${q.plan ?? 'No plan'} · valid until ${formatDate(q.valid_until)}`}
              aside={money(q.total, 2)}
              asideMeta={<StatusBadge status={q.status} />}
            />
          ))}
        </Panel>
        <Panel title="Invoices awaiting payment" action={<Link to="/invoices">Manage</Link>}>
          {data.invoices_awaiting_payment.length === 0 && <Empty title="Everything is settled">No confirmed invoices are open.</Empty>}
          {data.invoices_awaiting_payment.map((i) => (
            <ListRow
              key={i.id}
              to={`/invoices/${i.id}`}
              title={
                <>
                  <span className="mono">{i.number}</span> · {i.customer_detail.username}
                </>
              }
              meta={`Due ${formatDate(i.due_date)}`}
              aside={money(i.balance, 2)}
              asideMeta={<StatusBadge status={i.is_overdue ? 'overdue' : 'confirmed'} label={i.is_overdue ? 'overdue' : 'open'} />}
            />
          ))}
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
        <Panel title="Upcoming subscription renewals" subtitle="Next billing in the coming 30 days">
          {data.upcoming_renewals.length === 0 && <Empty title="No renewals due">Nothing bills in the next 30 days.</Empty>}
          {data.upcoming_renewals.map((r) => (
            <ListRow
              key={r.id}
              to={`/subscriptions/${r.id}`}
              title={
                <>
                  <span className="mono">{r.number}</span> · {r.customer}
                </>
              }
              meta={r.plan}
              aside={money(r.amount)}
              asideMeta={`Bills ${relativeDays(r.next_billing_date)}`}
            />
          ))}
        </Panel>
      </div>

      <div className="panel-grid">
        <Panel title="Recently created subscriptions" action={<Link to="/subscriptions">View all</Link>}>
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
              meta={s.plan_detail.name}
              aside={<StatusBadge status={s.status} />}
              asideMeta={formatDate(s.start_date)}
            />
          ))}
        </Panel>
        <Panel title="Recent customer activity">
          {data.recent_activities.length === 0 && <Empty title="No activity yet" />}
          {data.recent_activities.map((a, index) => (
            <ListRow
              key={index}
              title={a.text}
              meta={<span className="activity-type">{a.type}</span>}
              aside={formatDate(a.at)}
            />
          ))}
        </Panel>
      </div>
    </>
  )
}
