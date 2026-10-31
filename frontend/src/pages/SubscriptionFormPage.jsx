import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  PAYMENT_TERMS,
  computeTotals,
  createSubscription,
  emptyLine,
  errorMessage,
  getSubscription,
  loadCustomers,
  loadPlanOptions,
  loadProductOptions,
  updateSubscription,
} from '../api/subscriptions'
import { useToast } from '../components/Toast'
import { Field, FREQUENCY_LABEL, PageHeader, Panel, Skeleton, formatDate, money } from '../components/ui'
import SalesLinesEditor from './SalesLinesEditor'
import './Subscriptions.css'

const today = () => new Date().toISOString().slice(0, 10)

export default function SubscriptionFormPage() {
  const { id } = useParams()
  const isEditing = Boolean(id)
  const navigate = useNavigate()
  const toast = useToast()

  const [ready, setReady] = useState(false)
  const [customers, setCustomers] = useState([])
  const [plans, setPlans] = useState([])
  const [products, setProducts] = useState([])

  const [form, setForm] = useState({ customer: '', plan: '', start_date: today(), expiry_date: '', payment_terms: 'net_15' })
  const [lines, setLines] = useState([emptyLine()])
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    Promise.all([loadCustomers(), loadPlanOptions(), loadProductOptions(), isEditing ? getSubscription(id) : Promise.resolve(null)])
      .then(([customerList, planList, productList, existing]) => {
        setCustomers(customerList)
        setPlans(planList)
        setProducts(productList)
        if (existing) {
          setForm({
            customer: existing.customer,
            plan: existing.plan,
            start_date: existing.start_date,
            expiry_date: existing.expiry_date ?? '',
            payment_terms: existing.payment_terms,
          })
          setLines(
            existing.lines.map((line) => ({
              product: line.product,
              variant: line.variant ?? '',
              quantity: line.quantity,
              unit_price: line.unit_price,
              tax_rate: line.tax_rate ?? '',
            })),
          )
        }
        setReady(true)
      })
      .catch((err) => setLoadError(errorMessage(err, 'Could not load the form data.')))
  }, [id, isEditing])

  const plan = plans.find((p) => String(p.id) === String(form.plan))
  const totals = computeTotals(lines, products)
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  const expiryHint = plan?.end_date
    ? `Left blank, this follows the plan's end date, ${formatDate(plan.end_date)}.`
    : 'Left blank, the subscription expires one year after it starts.'

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrors({})
    setSubmitting(true)
    const payload = {
      ...form,
      expiry_date: form.expiry_date || null,
      lines: lines.map((line) => ({
        product: line.product,
        variant: line.variant || null,
        quantity: line.quantity,
        unit_price: line.unit_price,
        tax_rate: line.tax_rate === '' ? null : line.tax_rate,
      })),
    }
    if (!payload.expiry_date) delete payload.expiry_date
    try {
      const saved = isEditing ? await updateSubscription(id, payload) : await createSubscription(payload)
      toast.success(isEditing ? `${saved.number} updated.` : `${saved.number} created as a draft.`)
      navigate(`/subscriptions/${saved.id}`)
    } catch (err) {
      const data = err.response?.data
      setErrors(data && typeof data === 'object' && !Array.isArray(data) ? data : { detail: errorMessage(err) })
    } finally {
      setSubmitting(false)
    }
  }

  if (loadError) return <p className="form-error">{loadError}</p>
  if (!ready) {
    return (
      <div className="page-skeleton">
        <Skeleton height={34} width={300} radius={8} />
        <Skeleton height={420} radius={14} />
      </div>
    )
  }

  const linesError = errors.lines && (typeof errors.lines === 'string' || Array.isArray(errors.lines) ? [].concat(errors.lines).filter((x) => typeof x === 'string').join(' ') : '')

  return (
    <div>
      <PageHeader
        eyebrow="Sales"
        title={isEditing ? 'Edit subscription' : 'New subscription'}
        subtitle="It starts as a draft. Send a quotation or confirm it when the terms are agreed."
      />

      <form className="sub-form" onSubmit={handleSubmit}>
        <div className="stack">
          {(errors.detail || errors.non_field_errors) && <p className="form-error">{errors.detail ?? errors.non_field_errors}</p>}

          <Panel title="Agreement">
            <div className="form-row">
              <Field label="Customer" error={errors.customer}>
                <select value={form.customer} onChange={set('customer')} required>
                  <option value="">Select a customer</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.username} ({c.email})
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Plan" error={errors.plan}>
                <select value={form.plan} onChange={set('plan')} required>
                  <option value="">Select a plan</option>
                  {plans.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} · {p.product_name} · {money(p.price)} / {FREQUENCY_LABEL[p.billing_frequency]}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="form-row">
              <Field label="Start date" error={errors.start_date}>
                <input type="date" value={form.start_date} onChange={set('start_date')} required />
              </Field>
              <Field label="Expiry date" error={errors.expiry_date} hint={expiryHint}>
                <input type="date" value={form.expiry_date} min={form.start_date} onChange={set('expiry_date')} />
              </Field>
            </div>
            <Field label="Payment terms" error={errors.payment_terms} hint="Sets the due date on every invoice raised from this subscription.">
              <select value={form.payment_terms} onChange={set('payment_terms')}>
                {PAYMENT_TERMS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </Field>
          </Panel>

          <Panel title="Lines" subtitle="What the customer is billed for each period">
            {linesError && <p className="form-error">{linesError}</p>}
            <SalesLinesEditor lines={lines} onChange={setLines} products={products} taxMode="auto" minQuantity={plan?.min_quantity ?? 1} />
          </Panel>
        </div>

        <Panel title="Per billing period" className="summary-card">
          <div className="summary-line">
            <span>Subtotal</span>
            <span>{money(totals.subtotal, 2)}</span>
          </div>
          <div className="summary-line">
            <span>Tax</span>
            <span>{money(totals.tax, 2)}</span>
          </div>
          <div className="summary-line grand">
            <span>Total{plan ? ` per ${FREQUENCY_LABEL[plan.billing_frequency]}` : ''}</span>
            <span>{money(totals.total, 2)}</span>
          </div>
          <p className="summary-note">Tax follows the admin tax rules unless you set a rate on a line. Matching discounts are applied automatically when invoices are created.</p>
          {plan && plan.min_quantity > 1 && <p className="summary-note">This plan has a minimum quantity of {plan.min_quantity}.</p>}
          <div className="form-actions">
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? 'Saving...' : isEditing ? 'Save changes' : 'Create draft'}
            </button>
            <Link className="btn-ghost" to={isEditing ? `/subscriptions/${id}` : '/subscriptions'}>
              Cancel
            </Link>
          </div>
        </Panel>
      </form>
    </div>
  )
}
