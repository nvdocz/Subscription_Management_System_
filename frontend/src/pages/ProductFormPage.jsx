import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { addVariant, createProduct, deleteVariant, getProduct, updateProduct } from '../api/products'
import './Products.css'

const EMPTY_FORM = {
  name: '',
  product_type: 'goods',
  sales_price: '',
  cost_price: '',
  description: '',
  notes: '',
}

export default function ProductFormPage() {
  const { id } = useParams()
  const isEditing = Boolean(id)
  const navigate = useNavigate()

  const [form, setForm] = useState(EMPTY_FORM)
  const [variants, setVariants] = useState([])
  const [newVariant, setNewVariant] = useState({ name: '', extra_price: '' })
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [loading, setLoading] = useState(isEditing)

  useEffect(() => {
    if (!isEditing) return
    getProduct(id).then((data) => {
      setForm({
        name: data.name,
        product_type: data.product_type,
        sales_price: data.sales_price,
        cost_price: data.cost_price,
        description: data.description,
        notes: data.notes,
      })
      setVariants(data.variants)
      setLoading(false)
    })
  }, [id, isEditing])

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrors({})
    setSubmitting(true)
    try {
      if (isEditing) {
        await updateProduct(id, form)
        navigate('/products')
      } else {
        const created = await createProduct(form)
        navigate(`/products/${created.id}/edit`, { replace: true })
      }
    } catch (err) {
      setErrors(err.response?.data ?? { detail: 'Could not save product.' })
    } finally {
      setSubmitting(false)
    }
  }

  const handleAddVariant = async (e) => {
    e.preventDefault()
    if (!newVariant.name || !newVariant.extra_price) return
    try {
      const created = await addVariant(id, newVariant)
      setVariants((prev) => [...prev, created])
      setNewVariant({ name: '', extra_price: '' })
    } catch {
      setErrors({ variant: 'Could not add variant.' })
    }
  }

  const handleDeleteVariant = async (variantId) => {
    try {
      await deleteVariant(id, variantId)
      setVariants((prev) => prev.filter((v) => v.id !== variantId))
    } catch {
      setErrors({ variant: 'Could not delete variant.' })
    }
  }

  const fieldError = (field) => {
    const value = errors[field]
    if (!value) return null
    return Array.isArray(value) ? value.join(' ') : value
  }

  if (loading) return <p className="status-message">Loading product...</p>

  return (
    <div>
      <h1>{isEditing ? 'Edit product' : 'Add product'}</h1>
      <form className="product-form" onSubmit={handleSubmit}>
        {errors.detail && <p className="form-error">{errors.detail}</p>}
        <label>
          Product name
          <input name="name" value={form.name} onChange={handleChange} required />
          {fieldError('name') && <span className="field-error">{fieldError('name')}</span>}
        </label>
        <label>
          Product type
          <select name="product_type" value={form.product_type} onChange={handleChange}>
            <option value="goods">Goods</option>
            <option value="service">Service</option>
          </select>
        </label>
        <div className="form-row">
          <label>
            Sales price
            <input
              type="number"
              step="0.01"
              name="sales_price"
              value={form.sales_price}
              onChange={handleChange}
              required
            />
            {fieldError('sales_price') && <span className="field-error">{fieldError('sales_price')}</span>}
          </label>
          <label>
            Cost price
            <input
              type="number"
              step="0.01"
              name="cost_price"
              value={form.cost_price}
              onChange={handleChange}
              required
            />
            {fieldError('cost_price') && <span className="field-error">{fieldError('cost_price')}</span>}
          </label>
        </div>
        <label>
          Description
          <textarea name="description" value={form.description} onChange={handleChange} rows={3} />
        </label>
        <label>
          Notes
          <textarea name="notes" value={form.notes} onChange={handleChange} rows={2} />
        </label>
        <button type="submit" disabled={submitting}>
          {submitting ? 'Saving...' : isEditing ? 'Save changes' : 'Create product'}
        </button>
      </form>

      {isEditing && (
        <div className="variants-section">
          <h2>Variants</h2>
          {errors.variant && <p className="form-error">{errors.variant}</p>}
          <table className="products-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Extra price</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {variants.map((variant) => (
                <tr key={variant.id}>
                  <td>{variant.name}</td>
                  <td>{variant.extra_price}</td>
                  <td>
                    <button type="button" className="danger" onClick={() => handleDeleteVariant(variant.id)}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
              {variants.length === 0 && (
                <tr>
                  <td colSpan={3}>No variants yet.</td>
                </tr>
              )}
            </tbody>
          </table>
          <form className="variant-form" onSubmit={handleAddVariant}>
            <input
              placeholder="Variant name (e.g. Odoo integration)"
              value={newVariant.name}
              onChange={(e) => setNewVariant({ ...newVariant, name: e.target.value })}
            />
            <input
              type="number"
              step="0.01"
              placeholder="Extra price"
              value={newVariant.extra_price}
              onChange={(e) => setNewVariant({ ...newVariant, extra_price: e.target.value })}
            />
            <button type="submit">Add variant</button>
          </form>
        </div>
      )}
    </div>
  )
}
