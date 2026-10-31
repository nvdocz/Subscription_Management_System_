import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { createQuotation, fromItems, getQuotation, getTemplate, listTemplates, toItems, updateQuotation } from '../api/quotations'
import {
  PAYMENT_TERMS,
  computeTotals,
  emptyLine,
  errorMessage,
  loadCustomers,
  loadPlanOptions,
  loadProductOptions,
} from '../api/subscriptions'
import { useToast } from '../components/Toast'
import { Field, FREQUENCY_LABEL, PageHeader, Panel, Skeleton, money } from '../components/ui'
import SalesLinesEditor from './SalesLinesEditor'
import './Subscriptions.css'

export default function QuotationFormPage() {
  const { id } = useParams()
  const isEditing = Boolean(id)
  const navigate = useNavigate()
  const toast = useToast()

  const [ready, setReady] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [customers, setCustomers] = useState([])
  const [plans, setPlans] = useState([])
  const [products, setProducts] = useState([])
  const [templates, setTemplates] = useState([])

  const [form, setForm] = useState({ customer: '', plan: '', validity_days: 15, payment_terms: 'net_15', notes: '' })
  const [lines, setLines] = useState([emptyLine()])
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    Promise.all([loadCustomers(), loadPlanOptions(), loadProductOptions(), listTemplates(), isEditing ? getQuotation(id) : Promise.resolve(null)])
      .then(([customerList, planList, productList, templateList, quotation]) => {
        setCustomers(customerList)
        setPlans(planList)
        setProducts(productList)
        setTemplates(templateList)
        if (quotation) {
          setForm({
            customer: quotation.customer,
            plan: quotation.plan ?? '',
            validity_days: quotation.validity_days,
            payment_terms: quotation.payment_terms,
            notes: quotation.notes,
          })
          setLines(fromItems(quotation.items))
        }
        setReady(true)
      })
      .catch((err) => setLoadError(errorMessage(err, 'Could not load the form data.')))
  }, [id, isEditing])

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value })
  const plan = plans.find((p) => String(p.id) === String(form.plan))
  const totals = computeTotals(lines, products)

  const applyTemplate = async (templateId) => {
    if (!templateId) return
    try {
      const template = await getTemplate(templateId)
      setForm((prev) => ({ ...prev, plan: template.plan ?? '' }))
      setLines(fromItems(template.items))
      toast.success(`Loaded "${template.name}".`)
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrors({})
    setSubmitting(true)
    const payload = { ...form, plan: form.plan || null, items: toItems(lines, products) }
    try {
      const saved = isEditing ? await updateQuotation(id, payload) : await createQuotation(payload)
      toast.success(isEditing ? 'Quotation updated.' : `Quotation saved as a draft for ${saved.customer_detail.username}.`)
      navigate('/quotations')
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

  const itemsError = errors.items && [].concat(errors.items).filter((x) => typeof x === 'string').join(' ')

  return (
    <div>
      <PageHeader
        eyebrow="Sales"
        title={isEditing ? 'Edit quotation' : 'New quotation'}
        subtitle="Start from a template or build the offer line by line. Totals and tax update as you go."
      />

      <form className="sub-form" onSubmit={handleSubmit}>
        <div className="stack">
          {(errors.detail || errors.non_field_errors) && <p className="form-error">{errors.detail ?? errors.non_field_errors}</p>}

          <Panel title="Offer">
            {!isEditing && templates.length > 0 && (
              <Field label="Start from a template" hint="Fills the plan and product lines. You can still change everything.">
                <select defaultValue="" onChange={(e) => applyTemplate(e.target.value)}>
                  <option value="">Blank quotation</option>
                  {templates.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
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
              <Field label="Subscription plan" error={errors.plan} hint="Needed to convert the quotation into a subscription.">
                <select value={form.plan} onChange={set('plan')}>
                  <option value="">No plan yet</option>
                  {plans.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} · {p.product_name} · {money(p.price)} / {FREQUENCY_LABEL[p.billing_frequency]}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="form-row">
              <Field label="Valid for (days)" error={errors.validity_days}>
                <input type="number" min="1" value={form.validity_days} onChange={set('validity_days')} required />
              </Field>
              <Field label="Payment terms" error={errors.payment_terms}>
                <select value={form.payment_terms} onChange={set('payment_terms')}>
                  {PAYMENT_TERMS.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="Notes" error={errors.notes}>
              <textarea rows={2} value={form.notes} onChange={set('notes')} placeholder="Anything the customer should know" />
            </Field>
          </Panel>

          <Panel title="Items" subtitle="Tax is filled from each product's tax rule and can be overridden">
            {itemsError && <p className="form-error">{itemsError}</p>}
            <SalesLinesEditor lines={lines} onChange={setLines} products={products} taxMode="fill" minQuantity={plan?.min_quantity ?? 1} />
          </Panel>
        </div>

        <Panel title="Quotation total" className="summary-card">
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
          <p className="summary-note">The offer stays valid for {form.validity_days || 0} days from the day it is created.</p>
          <div className="form-actions">
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? 'Saving...' : isEditing ? 'Save changes' : 'Save draft'}
            </button>
            <Link className="btn-ghost" to="/quotations">
              Cancel
            </Link>
          </div>
        </Panel>
      </form>
    </div>
  )
}
