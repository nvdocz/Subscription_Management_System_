import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { PAYMENT_METHODS, createPayment, listOpenInvoices } from '../api/billing'
import { useToast } from '../components/Toast'
import { Empty, Field, PageHeader, Skeleton, formatDate, money } from '../components/ui'
import './Billing.css'

const today = () => new Date().toISOString().slice(0, 10)

export default function PaymentFormPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const [params] = useSearchParams()
  const [invoices, setInvoices] = useState(null)
  const [form, setForm] = useState({ invoice: params.get('invoice') ?? '', amount: '', method: 'bank_transfer', paid_on: today(), note: '' })
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let active = true
    listOpenInvoices().then((open) => {
      if (!active) return
      setInvoices(open)
      setForm((prev) => {
        const selected = open.find((i) => String(i.id) === String(prev.invoice))
        return selected ? { ...prev, amount: selected.balance } : prev
      })
    })
    return () => {
      active = false
    }
  }, [])

  const selected = invoices?.find((i) => String(i.id) === String(form.invoice))
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  const pickInvoice = (e) => {
    const next = invoices.find((i) => String(i.id) === e.target.value)
    setForm({ ...form, invoice: e.target.value, amount: next ? next.balance : '' })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrors({})
    setSubmitting(true)
    try {
      const payment = await createPayment(form)
      toast.success(`Payment of ${money(payment.amount, 2)} recorded against ${payment.invoice_number}.`)
      navigate(`/invoices/${payment.invoice}`)
    } catch (err) {
      setErrors(err.response?.data ?? { detail: 'Could not record the payment.' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Billing" title="Record payment" subtitle="Match money received to the invoice it settles." />

      {!invoices ? (
        <Skeleton height={380} radius={14} />
      ) : invoices.length === 0 ? (
        <div className="form-card">
          <Empty title="Nothing to collect">
            There are no confirmed invoices with an open balance. <Link to="/invoices">Review invoices</Link>
          </Empty>
        </div>
      ) : (
        <form className="form-card" onSubmit={handleSubmit}>
          {errors.detail && <p className="form-error">{errors.detail}</p>}

          <Field label="Invoice" error={errors.invoice}>
            <select value={form.invoice} onChange={pickInvoice} required>
              <option value="">Select an invoice</option>
              {invoices.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.number} · {i.customer_detail.username} · {money(i.balance, 2)} due
                </option>
              ))}
            </select>
          </Field>

          {selected && (
            <div className="run-note">
              <span>
                <strong className="mono">{selected.number}</strong> for {selected.customer_detail.username}: total {money(selected.amount, 2)},{' '}
                paid {money(selected.amount_paid, 2)}, due {formatDate(selected.due_date)}
                {selected.is_overdue ? ' (overdue)' : ''}.
              </span>
            </div>
          )}

          <div className="form-row">
            <Field label="Amount" error={errors.amount} hint={selected ? `Outstanding balance ${money(selected.balance, 2)}` : undefined}>
              <input type="number" step="0.01" min="0.01" value={form.amount} onChange={set('amount')} required />
            </Field>
            <Field label="Payment date" error={errors.paid_on}>
              <input type="date" value={form.paid_on} onChange={set('paid_on')} required />
            </Field>
          </div>

          <Field label="Method" error={errors.method}>
            <select value={form.method} onChange={set('method')}>
              {PAYMENT_METHODS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Note" error={errors.note} hint="Optional. A bank reference or cheque number helps reconciliation.">
            <input value={form.note} onChange={set('note')} maxLength={255} placeholder="e.g. NEFT ref 4471209" />
          </Field>

          <div className="form-actions">
            <button type="submit" disabled={submitting}>
              {submitting ? 'Saving...' : 'Record payment'}
            </button>
            <Link className="btn-ghost" to="/payments">
              Cancel
            </Link>
          </div>
        </form>
      )}
    </div>
  )
}
