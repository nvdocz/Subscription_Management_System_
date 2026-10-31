import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Pencil } from 'lucide-react'
import api from '../api/client'
import {
  ACTION_LABELS,
  STEPS,
  doSubscriptionAction,
  errorMessage,
  getSubscription,
  paymentTermsLabel,
} from '../api/subscriptions'
import { useConfirm, useToast } from '../components/Toast'
import {
  Empty,
  FREQUENCY_LABEL,
  PageHeader,
  Panel,
  Skeleton,
  Stepper,
  StatusBadge,
  Timeline,
  daysFromToday,
  formatDate,
  formatDateTime,
  money,
} from '../components/ui'
import { useAuth } from '../context/AuthContext'
import './Subscriptions.css'

const PRIMARY = ['send_quotation', 'confirm', 'activate', 'resume', 'renew']

const CUSTOMER_HINTS = {
  pause: 'Pause puts billing on hold. You can resume whenever you are ready.',
  resume: 'Resume restarts billing from today. Missed periods while paused are not charged.',
  close: 'Close ends the subscription early. Invoices already issued remain payable.',
  renew: 'Renew extends your expiry date by a year and keeps billing going.',
}

const CONFIRMS = {
  close: {
    title: 'Close this subscription?',
    message: 'Billing stops and the subscription is marked closed. Invoices already issued stay payable.',
    confirmLabel: 'Close subscription',
    tone: 'danger',
  },
  renew: {
    title: 'Renew this subscription?',
    message: 'The expiry date moves out by a year. A closed subscription starts billing again from today.',
    confirmLabel: 'Renew',
  },
}

const DONE = {
  send_quotation: 'Quotation sent.',
  confirm: 'Subscription confirmed.',
  activate: 'Subscription activated.',
  pause: 'Subscription paused.',
  resume: 'Subscription resumed.',
  close: 'Subscription closed.',
  renew: 'Subscription renewed.',
}

export default function SubscriptionDetailPage() {
  const { id } = useParams()
  const { user } = useAuth()
  const toast = useToast()
  const confirm = useConfirm()
  const isStaff = user.role !== 'customer'

  const [sub, setSub] = useState(null)
  const [invoices, setInvoices] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')

  const loadInvoices = useCallback(() => {
    api
      .get('/invoices/', { params: { subscription: id, page_size: 50 } })
      .then(({ data }) => setInvoices(data.results))
      .catch(() => setInvoices([]))
  }, [id])

  useEffect(() => {
    getSubscription(id)
      .then(setSub)
      .catch((err) => setError(errorMessage(err, 'We could not find that subscription.')))
    loadInvoices()
  }, [id, loadInvoices])

  const run = async (action) => {
    if (CONFIRMS[action] && !(await confirm(CONFIRMS[action]))) return
    setBusy(action)
    try {
      setSub(await doSubscriptionAction(id, action))
      toast.success(DONE[action])
      loadInvoices()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy('')
    }
  }

  if (error) {
    return (
      <div>
        <Link className="back-link" to="/subscriptions">
          <ArrowLeft size={15} /> Subscriptions
        </Link>
        <p className="form-error">{error}</p>
      </div>
    )
  }

  if (!sub) {
    return (
      <div className="page-skeleton">
        <Skeleton height={34} width={280} radius={8} />
        <Skeleton height={70} radius={12} />
        <Skeleton height={300} radius={12} />
      </div>
    )
  }

  const plan = sub.plan_detail
  const per = FREQUENCY_LABEL[plan.billing_frequency]
  const stepValue = sub.status === 'paused' ? 'active' : sub.status
  const expiryIn = daysFromToday(sub.expiry_date)
  const expiringSoon = ['active', 'paused'].includes(sub.status) && expiryIn !== null && expiryIn <= 30
  const editable = isStaff && ['draft', 'quotation'].includes(sub.status)
  const hints = !isStaff ? sub.allowed_actions.filter((a) => CUSTOMER_HINTS[a]) : []

  return (
    <div>
      <Link className="back-link" to="/subscriptions">
        <ArrowLeft size={15} /> {isStaff ? 'Subscriptions' : 'My subscriptions'}
      </Link>

      <PageHeader
        eyebrow="Subscription"
        title={
          <span className="title-with-badge">
            <span className="mono">{sub.number}</span>
            <StatusBadge status={sub.status} />
          </span>
        }
        subtitle={`${isStaff ? `${sub.customer_detail.username} on ` : ''}${plan.name} · ${plan.product_name}`}
        actions={
          <>
            {editable && (
              <Link className="btn-secondary" to={`/subscriptions/${sub.id}/edit`}>
                <Pencil size={15} /> Edit
              </Link>
            )}
            {sub.allowed_actions.map((action) => (
              <button
                key={action}
                type="button"
                className={action === 'close' ? 'btn-danger' : PRIMARY.includes(action) ? 'btn-primary' : 'btn-secondary'}
                disabled={Boolean(busy)}
                onClick={() => run(action)}
              >
                {busy === action ? 'Working...' : ACTION_LABELS[action]}
              </button>
            ))}
          </>
        }
      />

      <Panel className="stepper-panel">
        <Stepper steps={STEPS} current={stepValue} />
        {sub.status === 'paused' && <p className="stage-note">Paused. Billing is on hold until the subscription is resumed.</p>}
        {sub.status === 'confirmed' && (
          <p className="stage-note">Confirmed. It activates on its start date, {formatDate(sub.start_date)}, and the first invoice is issued then.</p>
        )}
        {expiringSoon && (
          <p className="stage-note warn">
            {expiryIn < 0 ? 'Expired' : expiryIn === 0 ? 'Expires today' : `Expires in ${expiryIn} days`} ({formatDate(sub.expiry_date)}).
            {sub.allowed_actions.includes('renew') ? ' Renew to keep billing going.' : ''}
          </p>
        )}
        {hints.length > 0 && (
          <ul className="action-hints">
            {hints.map((a) => (
              <li key={a}>
                <b>{ACTION_LABELS[a]}.</b> {CUSTOMER_HINTS[a]}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <div className="panel-grid wide-left">
        <div className="stack">
          <Panel title="Subscription lines" subtitle={`Billed every ${per}`} flush>
            <div className="table-card embedded">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th className="num">Qty</th>
                    <th className="num">Unit price</th>
                    <th className="num">Tax</th>
                    <th className="num">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {sub.lines.map((line) => (
                    <tr key={line.id}>
                      <td>
                        <div className="cell-stack">
                          <span className="strong">{line.product_name}</span>
                          {line.variant_name && <small>{line.variant_name}</small>}
                        </div>
                      </td>
                      <td className="num">{line.quantity}</td>
                      <td className="num">{money(line.unit_price, 2)}</td>
                      <td className="num">{Number(line.effective_tax_rate)}%</td>
                      <td className="num strong">{money(line.amount, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <dl className="totals">
              <div>
                <dt>Subtotal</dt>
                <dd>{money(sub.cycle_subtotal, 2)}</dd>
              </div>
              <div>
                <dt>Tax</dt>
                <dd>{money(sub.estimated_tax, 2)}</dd>
              </div>
              <div className="grand">
                <dt>Per {per}</dt>
                <dd>{money(sub.estimated_total, 2)}</dd>
              </div>
              <p>Before any discounts that apply at billing time.</p>
            </dl>
          </Panel>

          <Panel title="Invoices" subtitle="Billed from this subscription" flush>
            {invoices.length === 0 ? (
              <Empty title="No invoices yet">The first invoice is issued when the subscription becomes active.</Empty>
            ) : (
              <div className="table-card embedded">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Invoice</th>
                      <th>Status</th>
                      <th>Due</th>
                      <th className="num">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.map((invoice) => (
                      <tr key={invoice.id}>
                        <td>
                          <Link className="doc" to={`/invoices/${invoice.id}`}>
                            {invoice.number}
                          </Link>
                        </td>
                        <td>
                          <StatusBadge status={invoice.is_overdue ? 'overdue' : invoice.status} />
                        </td>
                        <td>{formatDate(invoice.due_date)}</td>
                        <td className="num strong">{money(invoice.amount, 2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>

        <div className="stack">
          <Panel title="Details">
            <dl className="facts">
              <div>
                <dt>Customer</dt>
                <dd>{sub.customer_detail.username}</dd>
              </div>
              <div>
                <dt>Plan</dt>
                <dd>
                  {plan.name} · {money(plan.price)} / {per}
                </dd>
              </div>
              <div>
                <dt>Payment terms</dt>
                <dd>{paymentTermsLabel(sub.payment_terms)}</dd>
              </div>
              <div>
                <dt>Start date</dt>
                <dd>{formatDate(sub.start_date)}</dd>
              </div>
              <div>
                <dt>Expiry date</dt>
                <dd>{formatDate(sub.expiry_date)}</dd>
              </div>
              <div>
                <dt>Next billing</dt>
                <dd>{sub.status === 'active' ? formatDate(sub.next_billing_date) : '—'}</dd>
              </div>
              {sub.end_date && (
                <div>
                  <dt>Closed on</dt>
                  <dd>{formatDate(sub.end_date)}</dd>
                </div>
              )}
            </dl>
          </Panel>

          <Panel title="History" subtitle="Every change, newest first">
            <Timeline
              items={sub.events.map((event) => ({
                title: event.message,
                meta: `${formatDateTime(event.created_at)}${event.actor_name ? ` · ${event.actor_name}` : ''}`,
              }))}
            />
          </Panel>
        </div>
      </div>
    </div>
  )
}
