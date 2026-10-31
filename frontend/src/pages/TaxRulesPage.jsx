import { useCallback, useEffect, useState } from 'react'
import { Percent, Plus } from 'lucide-react'
import { createTaxRule, deleteTaxRule, listSellableProducts, listTaxRules, updateTaxRule } from '../api/pricing'
import { useConfirm, useToast } from '../components/Toast'
import { Empty, Field, Modal, PageHeader, StatusBadge, TableSkeleton } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import './Billing.css'

const EMPTY = { name: '', rate: '', scope: 'all', product_type: 'goods', product: '', is_active: true }
const TYPE_LABEL = { goods: 'Goods', service: 'Services' }

function appliesTo(rule) {
  if (rule.scope === 'product') return { label: rule.product_name ?? 'One product', note: 'Specific product' }
  if (rule.scope === 'product_type') return { label: `All ${TYPE_LABEL[rule.product_type] ?? rule.product_type}`, note: 'Product type' }
  return { label: 'All products', note: 'Default rule' }
}

export default function TaxRulesPage() {
  const { user } = useAuth()
  const toast = useToast()
  const confirm = useConfirm()
  const isAdmin = user.role === 'admin'

  const [rules, setRules] = useState(null)
  const [products, setProducts] = useState([])
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => {
    return listTaxRules()
      .then(setRules)
      .catch(() => setError('Could not load tax rules.'))
  }, [])

  useEffect(() => {
    load()
    if (isAdmin) listSellableProducts().then(setProducts).catch(() => setProducts([]))
  }, [load, isAdmin])

  const open = (rule) => {
    setErrors({})
    setEditing(rule ?? {})
    setForm(
      rule
        ? {
            name: rule.name,
            rate: rule.rate,
            scope: rule.scope,
            product_type: rule.product_type || 'goods',
            product: rule.product ?? '',
            is_active: rule.is_active,
          }
        : EMPTY,
    )
  }

  const close = () => setEditing(null)
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErrors({})
    const payload = {
      name: form.name,
      rate: form.rate,
      is_active: form.is_active,
      product: form.scope === 'product' ? form.product || null : null,
      product_type: form.scope === 'product_type' ? form.product_type : '',
    }
    try {
      if (editing.id) await updateTaxRule(editing.id, payload)
      else await createTaxRule(payload)
      toast.success(editing.id ? 'Tax rule updated.' : 'Tax rule added.')
      close()
      load()
    } catch (err) {
      const data = err.response?.data
      setErrors(Array.isArray(data) ? { detail: data[0] } : (data ?? { detail: 'Could not save the rule.' }))
    } finally {
      setSaving(false)
    }
  }

  const toggle = async (rule) => {
    try {
      await updateTaxRule(rule.id, { is_active: !rule.is_active })
      load()
    } catch {
      toast.error('Could not change the rule.')
    }
  }

  const remove = async (rule) => {
    const ok = await confirm({
      title: `Delete "${rule.name}"?`,
      message: 'Invoices already issued keep their tax. Future invoices fall back to the next most specific rule.',
      confirmLabel: 'Delete rule',
      tone: 'danger',
    })
    if (!ok) return
    try {
      await deleteTaxRule(rule.id)
      toast.success('Tax rule deleted.')
      load()
    } catch {
      toast.error('Could not delete the rule.')
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Catalog"
        title="Tax rules"
        subtitle="Taxes are calculated automatically on every invoice from the rules below."
        actions={
          isAdmin && (
            <button type="button" className="btn-primary" onClick={() => open(null)}>
              <Plus size={16} /> Add tax rule
            </button>
          )
        }
      />

      <div className="explain-strip">
        <span>
          <strong>Most specific rule wins.</strong> A rule for one product beats a rule for a product type, which beats a rule for all
          products. If several active rules tie, the higher rate applies. {!isAdmin && 'Only admins can change rules.'}
        </span>
      </div>

      {error && <p className="form-error">{error}</p>}

      {!rules ? (
        <TableSkeleton rows={4} cols={5} />
      ) : (
        <div className="table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Rule</th>
                <th>Applies to</th>
                <th className="num">Rate</th>
                <th>Status</th>
                {isAdmin && <th />}
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => {
                const target = appliesTo(rule)
                return (
                  <tr key={rule.id}>
                    <td className="strong">{rule.name}</td>
                    <td>
                      {target.label}
                      <span className="cell-sub">{target.note}</span>
                    </td>
                    <td className="num">
                      <span className="rate-figure">{Number(rule.rate)}%</span>
                    </td>
                    <td>
                      <StatusBadge status={rule.is_active ? 'active' : 'disabled'} label={rule.is_active ? 'Active' : 'Disabled'} />
                    </td>
                    {isAdmin && (
                      <td className="table-actions">
                        <button type="button" onClick={() => open(rule)}>
                          Edit
                        </button>
                        <button type="button" onClick={() => toggle(rule)}>
                          {rule.is_active ? 'Disable' : 'Enable'}
                        </button>
                        <button type="button" className="danger" onClick={() => remove(rule)}>
                          Delete
                        </button>
                      </td>
                    )}
                  </tr>
                )
              })}
              {rules.length === 0 && (
                <tr>
                  <td colSpan={isAdmin ? 5 : 4} className="empty-cell">
                    <Empty icon={Percent} title="No tax rules yet">
                      Until a rule exists, invoices are issued with no tax.
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
        title={editing?.id ? 'Edit tax rule' : 'Add tax rule'}
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={close}>
              Cancel
            </button>
            <button type="submit" form="tax-rule-form" className="btn-primary" disabled={saving}>
              {saving ? 'Saving...' : 'Save rule'}
            </button>
          </>
        }
      >
        <form id="tax-rule-form" className="modal-form" onSubmit={save}>
          {(errors.detail || errors.non_field_errors) && <p className="form-error">{errors.detail ?? errors.non_field_errors}</p>}
          <div className="form-row">
            <Field label="Name" error={errors.name}>
              <input value={form.name} onChange={set('name')} placeholder="GST 18%" required />
            </Field>
            <Field label="Rate (%)" error={errors.rate}>
              <input type="number" min="0" max="100" step="0.01" value={form.rate} onChange={set('rate')} required />
            </Field>
          </div>
          <Field label="Applies to">
            <select value={form.scope} onChange={set('scope')}>
              <option value="all">All products</option>
              <option value="product_type">A product type</option>
              <option value="product">One product</option>
            </select>
          </Field>
          {form.scope === 'product_type' && (
            <Field label="Product type" error={errors.product_type}>
              <select value={form.product_type} onChange={set('product_type')}>
                <option value="goods">Goods</option>
                <option value="service">Services</option>
              </select>
            </Field>
          )}
          {form.scope === 'product' && (
            <Field label="Product" error={errors.product}>
              <select value={form.product} onChange={set('product')} required>
                <option value="">Select a product</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
          )}
          <label className="check-row">
            <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
            <span>
              Rule is active
              <small>Disabled rules are ignored when invoices are built.</small>
            </span>
          </label>
        </form>
      </Modal>
    </div>
  )
}
