import { useCallback, useEffect, useState } from 'react'
import { BadgePercent, Plus } from 'lucide-react'
import { createDiscount, deleteDiscount, listDiscounts, listSellableProducts, updateDiscount } from '../api/pricing'
import { useConfirm, useToast } from '../components/Toast'
import { Empty, Field, Modal, PageHeader, StatusBadge, TableSkeleton, formatDate, money } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import './Billing.css'

const EMPTY = {
  name: '',
  kind: 'percentage',
  value: '',
  applies_to: 'subscription',
  products: [],
  min_purchase: '0',
  min_quantity: '0',
  start_date: new Date().toISOString().slice(0, 10),
  end_date: '',
  usage_limit: '',
  is_active: true,
}

function valueLabel(d) {
  return d.kind === 'percentage' ? `${Number(d.value)}% off` : `${money(d.value, 2)} off`
}

function conditions(d) {
  const parts = []
  if (Number(d.min_purchase) > 0) parts.push(`Spend ${money(d.min_purchase)}+`)
  if (d.min_quantity > 0) parts.push(`${d.min_quantity}+ units`)
  return parts.length ? parts.join(' and ') : 'No minimum'
}

function UsageMeter({ discount }) {
  if (discount.usage_limit === null) {
    return <span className="list-meta">{discount.times_used} used, no limit</span>
  }
  const share = Math.min(100, Math.round((discount.times_used / discount.usage_limit) * 100))
  return (
    <div className="usage-meter">
      <span>
        {discount.times_used} / {discount.usage_limit} used
      </span>
      <div className={`usage-bar ${share >= 100 ? 'full' : ''}`}>
        <i style={{ width: `${share}%` }} />
      </div>
    </div>
  )
}

export default function DiscountsPage() {
  const { user } = useAuth()
  const toast = useToast()
  const confirm = useConfirm()
  const isAdmin = user.role === 'admin'

  const [discounts, setDiscounts] = useState(null)
  const [products, setProducts] = useState([])
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => {
    return listDiscounts()
      .then(setDiscounts)
      .catch(() => setError('Could not load discounts.'))
  }, [])

  useEffect(() => {
    load()
    if (isAdmin) listSellableProducts().then(setProducts).catch(() => setProducts([]))
  }, [load, isAdmin])

  const open = (discount) => {
    setErrors({})
    setEditing(discount ?? {})
    setForm(
      discount
        ? {
            name: discount.name,
            kind: discount.kind,
            value: discount.value,
            applies_to: discount.applies_to,
            products: discount.products,
            min_purchase: discount.min_purchase,
            min_quantity: String(discount.min_quantity),
            start_date: discount.start_date,
            end_date: discount.end_date ?? '',
            usage_limit: discount.usage_limit ?? '',
            is_active: discount.is_active,
          }
        : { ...EMPTY },
    )
  }

  const close = () => setEditing(null)
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value })
  const toggleProduct = (id) =>
    setForm((prev) => ({
      ...prev,
      products: prev.products.includes(id) ? prev.products.filter((p) => p !== id) : [...prev.products, id],
    }))

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErrors({})
    const payload = {
      ...form,
      products: form.applies_to === 'products' ? form.products : [],
      end_date: form.end_date || null,
      usage_limit: form.usage_limit === '' ? null : form.usage_limit,
      min_quantity: form.min_quantity || 0,
      min_purchase: form.min_purchase || 0,
    }
    try {
      if (editing.id) await updateDiscount(editing.id, payload)
      else await createDiscount(payload)
      toast.success(editing.id ? 'Discount updated.' : 'Discount created. It applies to upcoming invoices automatically.')
      close()
      load()
    } catch (err) {
      const data = err.response?.data
      setErrors(Array.isArray(data) ? { detail: data[0] } : (data ?? { detail: 'Could not save the discount.' }))
    } finally {
      setSaving(false)
    }
  }

  const toggle = async (discount) => {
    try {
      await updateDiscount(discount.id, { is_active: !discount.is_active })
      load()
    } catch {
      toast.error('Could not change the discount.')
    }
  }

  const remove = async (discount) => {
    const ok = await confirm({
      title: `Delete "${discount.name}"?`,
      message: 'Invoices that already used this discount keep it. It will not apply to any future invoice.',
      confirmLabel: 'Delete discount',
      tone: 'danger',
    })
    if (!ok) return
    try {
      await deleteDiscount(discount.id)
      toast.success('Discount deleted.')
      load()
    } catch {
      toast.error('Could not delete the discount.')
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Catalog"
        title="Discounts"
        subtitle="Rules that reward volume. They land on the next invoice by themselves and stop when they expire or run out."
        actions={
          isAdmin && (
            <button type="button" className="btn-primary" onClick={() => open(null)}>
              <Plus size={16} /> New discount
            </button>
          )
        }
      />

      <div className="explain-strip">
        <span>
          <strong>Nobody has to remember them.</strong> Every billing run checks the rules below. A discount applies when the invoice meets its
          minimums and dates, and each application counts against its usage limit. {!isAdmin && 'Only admins can change discounts.'}
        </span>
      </div>

      {error && <p className="form-error">{error}</p>}

      {!discounts ? (
        <TableSkeleton rows={4} cols={6} />
      ) : (
        <div className="table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Discount</th>
                <th>Applies to</th>
                <th>Conditions</th>
                <th>Valid</th>
                <th>Usage</th>
                <th>Status</th>
                {isAdmin && <th />}
              </tr>
            </thead>
            <tbody>
              {discounts.map((d) => (
                <tr key={d.id}>
                  <td>
                    <span className="strong">{d.name}</span>
                    <span className="cell-sub">{valueLabel(d)}</span>
                  </td>
                  <td>
                    {d.applies_to === 'subscription' ? 'Whole subscription' : d.product_names.join(', ') || 'Specific products'}
                  </td>
                  <td>{conditions(d)}</td>
                  <td>
                    {formatDate(d.start_date)}
                    <span className="cell-sub">{d.end_date ? `until ${formatDate(d.end_date)}` : 'no end date'}</span>
                  </td>
                  <td>
                    <UsageMeter discount={d} />
                  </td>
                  <td>
                    <StatusBadge status={d.status} />
                  </td>
                  {isAdmin && (
                    <td className="table-actions">
                      <button type="button" onClick={() => open(d)}>
                        Edit
                      </button>
                      <button type="button" onClick={() => toggle(d)}>
                        {d.is_active ? 'Disable' : 'Enable'}
                      </button>
                      <button type="button" className="danger" onClick={() => remove(d)}>
                        Delete
                      </button>
                    </td>
                  )}
                </tr>
              ))}
              {discounts.length === 0 && (
                <tr>
                  <td colSpan={isAdmin ? 7 : 6} className="empty-cell">
                    <Empty icon={BadgePercent} title="No discounts yet">
                      Create one to reward customers who take more seats or spend more.
                    </Empty>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={Boolean(editing)}
        onClose={close}
        wide
        title={editing?.id ? 'Edit discount' : 'New discount'}
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={close}>
              Cancel
            </button>
            <button type="submit" form="discount-form" className="btn-primary" disabled={saving}>
              {saving ? 'Saving...' : 'Save discount'}
            </button>
          </>
        }
      >
        <form id="discount-form" className="modal-form" onSubmit={save}>
          {(errors.detail || errors.non_field_errors) && <p className="form-error">{errors.detail ?? errors.non_field_errors}</p>}

          <Field label="Name" error={errors.name}>
            <input value={form.name} onChange={set('name')} placeholder="10% off for 3+ seats" required />
          </Field>

          <div className="form-row">
            <Field label="Type" error={errors.kind}>
              <select value={form.kind} onChange={set('kind')}>
                <option value="percentage">Percentage</option>
                <option value="fixed">Fixed amount</option>
              </select>
            </Field>
            <Field label={form.kind === 'percentage' ? 'Percent off' : 'Amount off (₹)'} error={errors.value}>
              <input type="number" min="0.01" step="0.01" max={form.kind === 'percentage' ? 100 : undefined} value={form.value} onChange={set('value')} required />
            </Field>
          </div>

          <Field label="Applies to" error={errors.applies_to}>
            <select value={form.applies_to} onChange={set('applies_to')}>
              <option value="subscription">Whole subscription</option>
              <option value="products">Specific products</option>
            </select>
          </Field>

          {form.applies_to === 'products' && (
            <div className="field">
              <span className="field-label">Products</span>
              <div className="multi-pick">
                {products.length === 0 && <span className="list-meta">No products available.</span>}
                {products.map((p) => (
                  <button key={p.id} type="button" className={form.products.includes(p.id) ? 'on' : ''} onClick={() => toggleProduct(p.id)}>
                    {p.name}
                  </button>
                ))}
              </div>
              {errors.products && <span className="field-error">{[].concat(errors.products).join(' ')}</span>}
            </div>
          )}

          <div className="form-row">
            <Field label="Minimum purchase (₹)" error={errors.min_purchase} hint="0 for no minimum">
              <input type="number" min="0" step="0.01" value={form.min_purchase} onChange={set('min_purchase')} />
            </Field>
            <Field label="Minimum quantity" error={errors.min_quantity} hint="0 for no minimum">
              <input type="number" min="0" step="1" value={form.min_quantity} onChange={set('min_quantity')} />
            </Field>
          </div>

          <div className="form-row">
            <Field label="Starts" error={errors.start_date}>
              <input type="date" value={form.start_date} onChange={set('start_date')} required />
            </Field>
            <Field label="Ends" error={errors.end_date} hint="Leave empty for no end">
              <input type="date" value={form.end_date} min={form.start_date || undefined} onChange={set('end_date')} />
            </Field>
            <Field label="Usage limit" error={errors.usage_limit} hint="Empty means unlimited">
              <input type="number" min="1" step="1" value={form.usage_limit} onChange={set('usage_limit')} />
            </Field>
          </div>

          <label className="check-row">
            <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
            <span>
              Discount is enabled
              <small>Disabled discounts never apply, whatever their dates.</small>
            </span>
          </label>
        </form>
      </Modal>
    </div>
  )
}
