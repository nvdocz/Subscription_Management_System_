import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { archiveProduct, deleteProduct, listProducts, unarchiveProduct } from '../api/products'
import './Products.css'

export default function ProductsPage() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = () => {
    setLoading(true)
    listProducts()
      .then(setProducts)
      .catch(() => setError('Could not load products.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleArchiveToggle = async (product) => {
    try {
      const updated = product.is_archived ? await unarchiveProduct(product.id) : await archiveProduct(product.id)
      setProducts((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
    } catch {
      setError('Could not update product status.')
    }
  }

  const handleDelete = async (product) => {
    if (!window.confirm(`Delete "${product.name}"? This cannot be undone.`)) return
    try {
      await deleteProduct(product.id)
      setProducts((prev) => prev.filter((p) => p.id !== product.id))
    } catch {
      setError('Could not delete product.')
    }
  }

  if (loading) return <p className="status-message">Loading products...</p>

  return (
    <div>
      <div className="products-header">
        <h1>Products</h1>
        <Link className="btn-primary" to="/products/new">
          Add product
        </Link>
      </div>
      {error && <p className="form-error">{error}</p>}
      <table className="products-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Sales price</th>
            <th>Cost price</th>
            <th>Variants</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {products.map((product) => (
            <tr key={product.id} className={product.is_archived ? 'archived-row' : ''}>
              <td>{product.name}</td>
              <td>{product.product_type}</td>
              <td>{product.sales_price}</td>
              <td>{product.cost_price}</td>
              <td>{product.variants.length}</td>
              <td>{product.is_archived ? 'Archived' : 'Active'}</td>
              <td className="row-actions">
                <Link to={`/products/${product.id}/edit`}>Edit</Link>
                <button type="button" onClick={() => handleArchiveToggle(product)}>
                  {product.is_archived ? 'Unarchive' : 'Archive'}
                </button>
                <button type="button" className="danger" onClick={() => handleDelete(product)}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
          {products.length === 0 && (
            <tr>
              <td colSpan={7}>No products yet.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
