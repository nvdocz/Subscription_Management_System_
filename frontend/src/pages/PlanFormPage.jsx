import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { FREQUENCIES, createPlan, getPlan, planAvailability, updatePlan } from '../api/plans'
import { listProducts } from '../api/products'
import { useToast } from '../components/Toast'
import { Field, PageHeader, Skeleton, StatusBadge, formatDate } from '../components/ui'
import './Billing.css'
import './Catalog.css'

const EMPTY = {
  product: '',
  name: '',
  price: '',
  billing_frequency: 'monthly',
  min_quantity: 1,
  start_date: new Date().toISOString().slice(0, 10),
  end_date: '',
  auto_close_enabled: false,
  allow_early_closure: true,
  allow_pause: true,
  allow_renewal: true,
}

const LIFECYCLE = [
  { key: 'auto_close_enabled', label: 'Close automatically at the end date', hint: 'Subscriptions on this plan close themselves when they expire.' },
  { key: 'allow_early_closure', label: 'Allow early closure', hint: 'Customers can end their subscription before it expires.' },
  { key: 'allow_pause', label: 'Allow pause', hint: 'Customers can put billing on hold and resume later.' },
  { key: 'allow_renewal', label: 'Allow renewal', hint: 'Customers can extend an expiring or closed subscription.' },
]

const AVAILABILITY = {
  available: { status: 'active', label: 'Available now' },
  scheduled: { status: 'scheduled', label: 'Not open yet' },
  ended: { status: 'expired', label: 'Ended' },
  inactive: { status: 'disabled', label: 'Switched off' },
}

export default function PlanFormPage() {
  const { id } = useParams()
  const isEditing = Boolean(id)
  const navigate = useNavigate()
  const toast = useToast()

  const [products, setProducts] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [active, setActive] = useState(true)
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [loaded, setLoaded] = useState(!isEditing)

  useEffect(() => {
    let live = true
    listProducts().then((list) => {
      if (!live) return
      const sellable = list.filter((p) => !p.is_archived)
      setProducts(sellable)
      if (!id && sellable.length > 0) setForm((prev) => ({ ...prev, product: prev.product || sellable[0].id }))
    })
    if (id) {
      getPlan(id).then((plan) => {
        if (!live) return
        setForm({
          product: plan.product,
          name: plan.name,
          price: plan.price,
          billing_frequency: plan.billing_frequency,
          min_quantity: plan.min_quantity,
          start_date: plan.start_date,
          end_date: plan.end_date ?? '',
          auto_close_enabled: plan.auto_close_enabled,
          allow_early_closure: plan.allow_early_closure,
          allow_pause: plan.allow_pause,
          allow_renewal: plan.allow_renewal,
        })
        setActive(plan.is_active)
        setLoaded(true)
      })
    }
    return () => {
      live = false
    }
  }, [id])

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrors({})
    setSubmitting(true)
    const payload = { ...form, end_date: form.end_date || null }
    try {
      if (isEditing) await updatePlan(id, payload)
      else await createPlan(payload)
      toast.success(isEditing ? 'Plan saved.' : 'Plan created.')
      navigate('/plans')
    } catch (err) {
      const data = err.response?.data
      setErrors(Array.isArray(data) ? { detail: data[0] } : (data ?? { detail: 'Could not save the plan.' }))
    } finally {
      setSubmitting(false)
    }
  }

  if (!loaded || !products) return <Skeleton height={460} radius={14} />

  const availability = AVAILABILITY[planAvailability({ is_active: active, start_date: form.start_date, end_date: form.end_date || null })]
  const autoCloseWithoutEnd = form.auto_close_enabled && !form.end_date

  return (
    <div>
      <PageHeader
        eyebrow="Catalog"
        title={isEditing ? 'Edit plan' : 'Create plan'}
        subtitle="Price, billing rhythm, the dates it is on sale and what customers may do with it."
      />

      <form className="form-card wide" onSubmit={handleSubmit}>
        {errors.detail && <p className="form-error">{errors.detail}</p>}
        {errors.non_field_errors && <p className="form-error">{errors.non_field_errors}</p>}

        <div className="form-row">
          <Field label="Product" error={errors.product}>
            <select value={form.product} onChange={set('product')} required>
              {products.length === 0 && <option value="">No active products</option>}
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Plan name" error={errors.name}>
            <input value={form.name} onChange={set('name')} placeholder="Professional" required />
          </Field>
        </div>

        <div className="form-row">
          <Field label="Price (₹)" error={errors.price}>
            <input type="number" min="0" step="0.01" value={form.price} onChange={set('price')} required />
          </Field>
          <Field label="Billing frequency" error={errors.billing_frequency}>
            <select value={form.billing_frequency} onChange={set('billing_frequency')}>
              {FREQUENCIES.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Minimum quantity" error={errors.min_quantity}>
            <input type="number" min="1" step="1" value={form.min_quantity} onChange={set('min_quantity')} required />
          </Field>
        </div>

        <div className="form-row">
          <Field label="Available from" error={errors.start_date}>
            <input type="date" value={form.start_date} onChange={set('start_date')} required />
          </Field>
          <Field label="Available until" error={errors.end_date} hint="Leave empty to keep it on sale.">
            <input type="date" value={form.end_date} min={form.start_date || undefined} onChange={set('end_date')} />
          </Field>
        </div>

        <div className="availability-line">
          <StatusBadge status={availability.status} label={availability.label} />
          <span>
            {form.end_date ? `On sale ${formatDate(form.start_date)} to ${formatDate(form.end_date)}.` : `On sale from ${formatDate(form.start_date)}, no end date.`}
          </span>
        </div>

        <div className="lifecycle-group">
          <span className="field-label">Lifecycle options</span>
          {LIFECYCLE.map((option) => (
            <label key={option.key} className="check-row">
              <input
                type="checkbox"
                checked={form[option.key]}
                onChange={(e) => setForm({ ...form, [option.key]: e.target.checked })}
              />
              <span>
                {option.label}
                <small>{option.hint}</small>
              </span>
            </label>
          ))}
          {autoCloseWithoutEnd && (
            <p className="form-error">Automatic closure needs an end date, otherwise there is nothing to close at.</p>
          )}
        </div>

        <div className="form-actions">
          <button type="submit" disabled={submitting}>
            {submitting ? 'Saving...' : isEditing ? 'Save changes' : 'Create plan'}
          </button>
          <Link className="btn-ghost" to="/plans">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  )
}
