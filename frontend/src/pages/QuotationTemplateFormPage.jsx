import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { createTemplate, toItems } from '../api/quotations'
import { computeTotals, emptyLine, errorMessage, loadPlanOptions, loadProductOptions } from '../api/subscriptions'
import { useToast } from '../components/Toast'
import { Field, FREQUENCY_LABEL, PageHeader, Panel, Skeleton, money } from '../components/ui'
import SalesLinesEditor from './SalesLinesEditor'
import './Subscriptions.css'

export default function QuotationTemplateFormPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const [ready, setReady] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [plans, setPlans] = useState([])
  const [products, setProducts] = useState([])
  const [form, setForm] = useState({ name: '', plan: '', notes: '' })
  const [lines, setLines] = useState([emptyLine()])
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    Promise.all([loadPlanOptions(), loadProductOptions()])
      .then(([planList, productList]) => {
        setPlans(planList)
        setProducts(productList)
        setReady(true)
      })
      .catch((err) => setLoadError(errorMessage(err, 'Could not load the form data.')))
  }, [])

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value })
  const plan = plans.find((p) => String(p.id) === String(form.plan))
  const totals = computeTotals(lines, products)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrors({})
    setSubmitting(true)
    try {
      await createTemplate({ ...form, plan: form.plan || null, items: toItems(lines, products) })
      toast.success('Template saved.')
      navigate('/quotation-templates')
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
        <Skeleton height={360} radius={14} />
      </div>
    )
  }

  const itemsError = errors.items && [].concat(errors.items).filter((x) => typeof x === 'string').join(' ')

  return (
    <div>
      <PageHeader eyebrow="Sales" title="New quotation template" subtitle="Save the plan and lines you quote most often." />

      <form className="sub-form" onSubmit={handleSubmit}>
        <div className="stack">
          {(errors.detail || errors.non_field_errors) && <p className="form-error">{errors.detail ?? errors.non_field_errors}</p>}
          <Panel title="Template">
            <Field label="Name" error={errors.name}>
              <input value={form.name} onChange={set('name')} required placeholder="e.g. Mid-size team starter" autoFocus />
            </Field>
            <Field label="Subscription plan" error={errors.plan}>
              <select value={form.plan} onChange={set('plan')}>
                <option value="">No plan attached</option>
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} · {p.product_name} · {money(p.price)} / {FREQUENCY_LABEL[p.billing_frequency]}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Notes" error={errors.notes}>
              <textarea rows={2} value={form.notes} onChange={set('notes')} />
            </Field>
          </Panel>

          <Panel title="Items">
            {itemsError && <p className="form-error">{itemsError}</p>}
            <SalesLinesEditor lines={lines} onChange={setLines} products={products} taxMode="fill" minQuantity={plan?.min_quantity ?? 1} />
          </Panel>
        </div>

        <Panel title="Template total" className="summary-card">
          <div className="summary-line">
            <span>Subtotal</span>
            <span>{money(totals.subtotal, 2)}</span>
          </div>
          <div className="summary-line">
            <span>Tax</span>
            <span>{money(totals.tax, 2)}</span>
          </div>
          <div className="summary-line grand">
            <span>Total</span>
            <span>{money(totals.total, 2)}</span>
          </div>
          <div className="form-actions">
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? 'Saving...' : 'Save template'}
            </button>
            <Link className="btn-ghost" to="/quotation-templates">
              Cancel
            </Link>
          </div>
        </Panel>
      </form>
    </div>
  )
}
