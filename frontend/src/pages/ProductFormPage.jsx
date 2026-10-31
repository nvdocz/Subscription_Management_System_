import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Plus, X } from 'lucide-react'
import { addVariant, createProduct, deleteVariant, getProduct, updateProduct } from '../api/products'
import { useToast } from '../components/Toast'
import { Field, PageHeader, Panel, Skeleton, money } from '../components/ui'
import './Billing.css'
import './Catalog.css'

const EMPTY = { name: '', product_type: 'service', sales_price: '', cost_price: '', description: '', notes: '' }

export default function ProductFormPage() {
  const { id } = useParams()
  const isEditing = Boolean(id)
  const navigate = useNavigate()
  const toast = useToast()

  const [form, setForm] = useState(EMPTY)
  const [variants, setVariants] = useState([])
  const [newVariant, setNewVariant] = useState({ name: '', extra_price: '' })
  const [errors, setErrors] = useState({})
  const [variantError, setVariantError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [loaded, setLoaded] = useState(!isEditing)

  useEffect(() => {
    if (!id) return undefined
    let active = true
    getProduct(id).then((data) => {
      if (!active) return
      setForm({
        name: data.name,
        product_type: data.product_type,
        sales_price: data.sales_price,
        cost_price: data.cost_price,
        description: data.description,
        notes: data.notes,
      })
      setVariants(data.variants)
      setLoaded(true)
    })
    return () => {
      active = false
    }
  }, [id])

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrors({})
    setSubmitting(true)
    try {
      if (isEditing) {
        await updateProduct(id, form)
        toast.success('Product saved.')
        navigate('/products')
      } else {
        const created = await createProduct(form)
        toast.success('Product created. Add variants below if it comes in more than one flavour.')
        navigate(`/products/${created.id}/edit`, { replace: true })
      }
    } catch (err) {
      setErrors(err.response?.data ?? { detail: 'Could not save the product.' })
    } finally {
      setSubmitting(false)
    }
  }

  const handleAddVariant = async (e) => {
    e.preventDefault()
    setVariantError('')
    try {
      const created = await addVariant(id, newVariant)
      setVariants((prev) => [...prev, created])
      setNewVariant({ name: '', extra_price: '' })
    } catch (err) {
      const data = err.response?.data
      setVariantError(data?.name?.[0] ?? data?.extra_price?.[0] ?? 'Could not add the variant.')
    }
  }

  const handleDeleteVariant = async (variant) => {
    try {
      await deleteVariant(id, variant.id)
      setVariants((prev) => prev.filter((v) => v.id !== variant.id))
    } catch {
      toast.error('Could not remove the variant.')
    }
  }

  if (!loaded) return <Skeleton height={420} radius={14} />

  return (
    <div>
      <PageHeader
        eyebrow="Catalog"
        title={isEditing ? form.name || 'Edit product' : 'Add product'}
        subtitle={isEditing ? 'Pricing, notes and variants.' : 'Set the name, price and cost. Variants can be added once it is saved.'}
      />

      <div className="editor-grid">
        <form className="form-card wide" style={{ maxWidth: 'none' }} onSubmit={handleSubmit}>
          {errors.detail && <p className="form-error">{errors.detail}</p>}

          <div className="form-row">
            <Field label="Product name" error={errors.name}>
              <input value={form.name} onChange={set('name')} required />
            </Field>
            <Field label="Product type" error={errors.product_type}>
              <select value={form.product_type} onChange={set('product_type')}>
                <option value="service">Service</option>
                <option value="goods">Goods</option>
              </select>
            </Field>
          </div>

          <div className="form-row">
            <Field label="Sales price (₹)" error={errors.sales_price}>
              <input type="number" step="0.01" min="0" value={form.sales_price} onChange={set('sales_price')} required />
            </Field>
            <Field label="Cost price (₹)" error={errors.cost_price} hint="Internal only. Customers never see this.">
              <input type="number" step="0.01" min="0" value={form.cost_price} onChange={set('cost_price')} required />
            </Field>
          </div>

          <Field label="Description" error={errors.description}>
            <textarea rows={3} value={form.description} onChange={set('description')} />
          </Field>
          <Field label="Internal notes" error={errors.notes}>
            <textarea rows={3} value={form.notes} onChange={set('notes')} />
          </Field>

          <div className="form-actions">
            <button type="submit" disabled={submitting}>
              {submitting ? 'Saving...' : isEditing ? 'Save changes' : 'Create product'}
            </button>
            <Link className="btn-ghost" to="/products">
              Cancel
            </Link>
          </div>
        </form>

        <Panel title="Variants" subtitle="Brands or editions that add to the base price">
          {!isEditing ? (
            <p className="variant-hint">Save the product first, then add variants such as an Odoo edition at +₹560.</p>
          ) : (
            <>
              {variants.length === 0 ? (
                <p className="variant-hint" style={{ marginTop: 0, marginBottom: 14 }}>
                  No variants. The product sells at its base price.
                </p>
              ) : (
                <ul className="variant-list">
                  {variants.map((variant) => (
                    <li key={variant.id}>
                      <span className="variant-name">{variant.name}</span>
                      <span className="variant-price">+ {money(variant.extra_price, 2)}</span>
                      <button type="button" className="icon-btn" onClick={() => handleDeleteVariant(variant)} aria-label={`Remove ${variant.name}`}>
                        <X size={15} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              <form className="variant-add" onSubmit={handleAddVariant}>
                <input
                  placeholder="Variant, e.g. Odoo"
                  value={newVariant.name}
                  onChange={(e) => setNewVariant({ ...newVariant, name: e.target.value })}
                  required
                  aria-label="Variant name"
                />
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="Extra ₹"
                  value={newVariant.extra_price}
                  onChange={(e) => setNewVariant({ ...newVariant, extra_price: e.target.value })}
                  required
                  aria-label="Extra price"
                />
                <button type="submit" className="btn-secondary">
                  <Plus size={15} /> Add
                </button>
              </form>
              {variantError && (
                <p className="form-error" style={{ marginTop: 10 }}>
                  {variantError}
                </p>
              )}
            </>
          )}
        </Panel>
      </div>
    </div>
  )
}
