import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, BellRing, CheckCheck, CreditCard, HandCoins, Mail, Printer, XCircle } from 'lucide-react'
import { getInvoice, invoiceAction } from '../api/billing'
import { BrandMark, Wordmark } from '../components/Brand'
import { useConfirm, useToast } from '../components/Toast'
import { Empty, Skeleton, Stepper, StatusBadge, formatDate, formatDateTime, money } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import './Invoice.css'

const STEPS = [
  { value: 'draft', label: 'Draft' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'paid', label: 'Paid' },
]

const METHOD_LABEL = { card: 'Card', bank_transfer: 'Bank transfer', upi: 'UPI', cash: 'Cash', cheque: 'Cheque' }

const ACTIONS = {
  confirm: {
    label: 'Confirm invoice',
    icon: CheckCheck,
    primary: true,
    success: 'Invoice confirmed.',
  },
  send: { label: 'Send by email', icon: Mail, success: 'Invoice emailed to the customer.' },
  remind: { label: 'Send reminder', icon: BellRing, success: 'Payment reminder sent.' },
  cancel: {
    label: 'Cancel invoice',
    icon: XCircle,
    danger: true,
    success: 'Invoice cancelled.',
    dialog: {
      title: 'Cancel this invoice?',
      message: 'A cancelled invoice can no longer be paid or confirmed. Cancelling does not move the billing date of the subscription back.',
      confirmLabel: 'Cancel invoice',
      tone: 'danger',
    },
  },
  pay: {
    label: 'Pay now',
    icon: CreditCard,
    primary: true,
    success: 'Payment received. Thank you.',
    dialog: {
      title: 'Pay this invoice?',
      message: 'This uses the demo payment gateway and settles the full outstanding balance with a card payment.',
      confirmLabel: 'Pay balance',
    },
  },
}

export default function InvoiceDetailPage() {
  const { id } = useParams()
  const { user } = useAuth()
  const toast = useToast()
  const confirm = useConfirm()
  const isCustomer = user.role === 'customer'
  const [invoice, setInvoice] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')

  useEffect(() => {
    let active = true
    getInvoice(id)
      .then((data) => active && setInvoice(data))
      .catch(() => active && setError('This invoice could not be found.'))
    return () => {
      active = false
    }
  }, [id])

  const run = async (name) => {
    const config = ACTIONS[name]
    if (config.dialog && !(await confirm(config.dialog))) return
    setBusy(name)
    try {
      setInvoice(await invoiceAction(id, name))
      toast.success(config.success)
    } catch (err) {
      const data = err.response?.data
      toast.error((Array.isArray(data) ? data[0] : data?.detail) ?? 'That action could not be completed.')
    } finally {
      setBusy('')
    }
  }

  if (error) {
    return (
      <div className="invoice-page">
        <Empty title="Invoice not found">{error}</Empty>
        <p className="center-link">
          <Link to="/invoices">Back to invoices</Link>
        </p>
      </div>
    )
  }

  if (!invoice) {
    return (
      <div className="invoice-page">
        <Skeleton height={40} width={320} radius={8} />
        <div style={{ height: 18 }} />
        <Skeleton height={560} radius={14} />
      </div>
    )
  }

  const displayStatus = invoice.is_overdue ? 'overdue' : invoice.status
  const actions = invoice.allowed_actions ?? []
  const canRecord = !isCustomer && invoice.status === 'confirmed'

  return (
    <div className="invoice-page">
      <div className="invoice-toolbar no-print">
        <Link className="back-link" to="/invoices">
          <ArrowLeft size={15} /> Invoices
        </Link>

        <div className="invoice-flow">
          {invoice.status === 'cancelled' ? (
            <StatusBadge status="cancelled" />
          ) : (
            <Stepper steps={STEPS} current={invoice.status} />
          )}
        </div>

        <div className="invoice-actions">
          {canRecord && (
            <Link className="btn-secondary" to={`/payments/new?invoice=${invoice.id}`}>
              <HandCoins size={16} /> Record payment
            </Link>
          )}
          {['confirm', 'send', 'remind', 'pay', 'cancel']
            .filter((name) => actions.includes(name))
            .map((name) => {
              const { label, icon: Icon, primary, danger } = ACTIONS[name]
              return (
                <button
                  key={name}
                  type="button"
                  className={primary ? 'btn-primary' : danger ? 'btn-danger' : 'btn-secondary'}
                  disabled={busy === name}
                  onClick={() => run(name)}
                >
                  <Icon size={16} /> {busy === name ? 'Working...' : label}
                </button>
              )
            })}
          <button type="button" className="btn-secondary" onClick={() => window.print()}>
            <Printer size={16} /> Print
          </button>
        </div>
      </div>

      <article className="invoice-doc">
        <header className="doc-head">
          <div className="doc-brand">
            <BrandMark size={40} />
            <Wordmark />
            <address>
              Brightloop Software
              <br />
              Recurring billing desk
            </address>
          </div>
          <div className="doc-title">
            <span>Invoice</span>
            <strong className="mono">{invoice.number}</strong>
            <StatusBadge status={displayStatus} />
          </div>
        </header>

        <section className="doc-meta">
          <div>
            <span>Billed to</span>
            <strong>{invoice.customer_detail.username}</strong>
            <em>{invoice.customer_detail.email}</em>
          </div>
          <div>
            <span>Issued</span>
            <strong>{formatDate(invoice.issue_date)}</strong>
          </div>
          <div>
            <span>Due</span>
            <strong className={invoice.is_overdue ? 'late' : ''}>{formatDate(invoice.due_date)}</strong>
          </div>
          <div>
            <span>Billing period</span>
            <strong>
              {invoice.period_start ? `${formatDate(invoice.period_start)} to ${formatDate(invoice.period_end)}` : '—'}
            </strong>
          </div>
          <div>
            <span>Subscription</span>
            {invoice.subscription ? (
              <Link className="mono" to={`/subscriptions/${invoice.subscription}`}>
                {invoice.subscription_number}
              </Link>
            ) : (
              <strong>—</strong>
            )}
            {invoice.plan_name && <em>{invoice.plan_name} plan</em>}
          </div>
        </section>

        <table className="doc-lines">
          <thead>
            <tr>
              <th>Description</th>
              <th className="num">Qty</th>
              <th className="num">Unit price</th>
              <th className="num">Tax</th>
              <th className="num">Discount</th>
              <th className="num">Amount</th>
            </tr>
          </thead>
          <tbody>
            {invoice.lines.map((line) => (
              <tr key={line.id}>
                <td>{line.description}</td>
                <td className="num">{line.quantity}</td>
                <td className="num">{money(line.unit_price, 2)}</td>
                <td className="num">{Number(line.tax_rate)}%</td>
                <td className="num">{Number(line.discount_amount) ? `− ${money(line.discount_amount, 2)}` : '—'}</td>
                <td className="num strong">{money(line.total, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <section className="doc-foot">
          <div className="doc-notes">
            {invoice.discounts.length > 0 && (
              <>
                <h3>Discounts applied</h3>
                <ul>
                  {invoice.discounts.map((d) => (
                    <li key={d.id}>
                      <span>{d.name}</span>
                      <b>− {money(d.amount, 2)}</b>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {invoice.notes && (
              <>
                <h3>Notes</h3>
                <p>{invoice.notes}</p>
              </>
            )}
            {invoice.sent_at && <p className="doc-trail">Emailed {formatDateTime(invoice.sent_at)}</p>}
            {invoice.last_reminder_at && <p className="doc-trail">Reminder sent {formatDateTime(invoice.last_reminder_at)}</p>}
          </div>

          <dl className="doc-totals">
            <div>
              <dt>Subtotal</dt>
              <dd>{money(invoice.subtotal, 2)}</dd>
            </div>
            <div>
              <dt>Discount</dt>
              <dd>{Number(invoice.discount_total) ? `− ${money(invoice.discount_total, 2)}` : money(0, 2)}</dd>
            </div>
            <div>
              <dt>Tax</dt>
              <dd>{money(invoice.tax_total, 2)}</dd>
            </div>
            <div className="grand">
              <dt>Total</dt>
              <dd>{money(invoice.amount, 2)}</dd>
            </div>
            <div>
              <dt>Paid</dt>
              <dd>{money(invoice.amount_paid, 2)}</dd>
            </div>
            <div className={`due ${Number(invoice.balance) > 0 && invoice.status === 'confirmed' ? 'owing' : ''}`}>
              <dt>Balance due</dt>
              <dd>{invoice.status === 'cancelled' ? money(0, 2) : money(invoice.balance, 2)}</dd>
            </div>
          </dl>
        </section>

        <section className="doc-payments">
          <h3>Payments</h3>
          {invoice.payments.length === 0 ? (
            <p className="doc-trail">No payments recorded yet.</p>
          ) : (
            <table className="doc-lines compact">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Method</th>
                  <th>Note</th>
                  <th className="num">Amount</th>
                </tr>
              </thead>
              <tbody>
                {invoice.payments.map((p) => (
                  <tr key={p.id}>
                    <td>{formatDate(p.paid_on)}</td>
                    <td>{METHOD_LABEL[p.method] ?? p.method}</td>
                    <td>{p.note || '—'}</td>
                    <td className="num strong">{money(p.amount, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <footer className="doc-end">Thank you for your business. Questions about this invoice? Reply to the email it was sent with.</footer>
      </article>
    </div>
  )
}
