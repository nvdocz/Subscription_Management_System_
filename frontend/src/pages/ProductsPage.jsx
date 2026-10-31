import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Package, Plus } from 'lucide-react'
import { archiveProduct, deleteProduct, listProducts, unarchiveProduct } from '../api/products'
import { useConfirm, useToast } from '../components/Toast'
import { Empty, FilterTabs, PageHeader, SearchInput, StatusBadge, TableSkeleton, money } from '../components/ui'
import './Billing.css'
import './Catalog.css'

const TYPE_LABEL = { goods: 'Goods', service: 'Service' }

function margin(product) {
  const sales = Number(product.sales_price)
  if (!sales) return null
  return Math.round(((sales - Number(product.cost_price)) / sales) * 100)
}

export default function ProductsPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()
  const [products, setProducts] = useState(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('active')
  const [search, setSearch] = useState('')

  const load = useCallback(() => {
    return listProducts()
      .then(setProducts)
      .catch(() => setError('Could not load products.'))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const counts = useMemo(() => {
    const all = products ?? []
    return { active: all.filter((p) => !p.is_archived).length, archived: all.filter((p) => p.is_archived).length, all: all.length }
  }, [products])

  const visible = useMemo(() => {
    const term = search.trim().toLowerCase()
    return (products ?? []).filter((p) => {
      if (tab === 'active' && p.is_archived) return false
      if (tab === 'archived' && !p.is_archived) return false
      return !term || p.name.toLowerCase().includes(term) || p.description.toLowerCase().includes(term)
    })
  }, [products, tab, search])

  const toggleArchive = async (product) => {
    try {
      const updated = product.is_archived ? await unarchiveProduct(product.id) : await archiveProduct(product.id)
      setProducts((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
      toast.success(`${product.name} ${product.is_archived ? 'restored' : 'archived'}.`)
    } catch {
      toast.error('Could not change the product status.')
    }
  }

  const remove = async (product) => {
    const ok = await confirm({
      title: `Delete "${product.name}"?`,
      message: 'This also removes its variants and any plans built on it. Archive it instead if you only want to stop selling it.',
      confirmLabel: 'Delete product',
      tone: 'danger',
    })
    if (!ok) return
    try {
      await deleteProduct(product.id)
      setProducts((prev) => prev.filter((p) => p.id !== product.id))
      toast.success('Product deleted.')
    } catch {
      toast.error('Could not delete the product.')
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Catalog"
        title="Products"
        subtitle="What Brightloop sells. Plans are built on these, and variants add to the price."
        actions={
          <Link className="btn-primary" to="/products/new">
            <Plus size={16} /> Add product
          </Link>
        }
      />

      <div className="toolbar">
        <FilterTabs
          tabs={[
            { value: 'active', label: 'Active', count: counts.active },
            { value: 'archived', label: 'Archived', count: counts.archived },
            { value: 'all', label: 'All', count: counts.all },
          ]}
          value={tab}
          onChange={setTab}
        />
        <SearchInput value={search} onChange={setSearch} placeholder="Search products" />
      </div>

      {error && <p className="form-error">{error}</p>}

      {!products ? (
        <TableSkeleton rows={5} cols={7} />
      ) : (
        <div className="table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Type</th>
                <th className="num">Sales price</th>
                <th className="num">Cost price</th>
                <th className="num">Variants</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {visible.map((product) => {
                const m = margin(product)
                return (
                  <tr
                    key={product.id}
                    className={`row-link ${product.is_archived ? 'row-archived' : ''}`}
                    onClick={() => navigate(`/products/${product.id}/edit`)}
                  >
                    <td>
                      <div className="product-name-cell">
                        <span className="strong">{product.name}</span>
                        {product.description && <small>{product.description}</small>}
                      </div>
                    </td>
                    <td>{TYPE_LABEL[product.product_type] ?? product.product_type}</td>
                    <td className="num strong">{money(product.sales_price, 2)}</td>
                    <td className="num">
                      {money(product.cost_price, 2)}
                      {m !== null && <div className={`margin-figure ${m > 0 ? 'good' : ''}`}>{m}% margin</div>}
                    </td>
                    <td className="num">{product.variants.length}</td>
                    <td>
                      <StatusBadge status={product.is_archived ? 'closed' : 'active'} label={product.is_archived ? 'Archived' : 'Active'} />
                    </td>
                    <td className="table-actions" onClick={(e) => e.stopPropagation()}>
                      <Link to={`/products/${product.id}/edit`}>Edit</Link>
                      <button type="button" onClick={() => toggleArchive(product)}>
                        {product.is_archived ? 'Restore' : 'Archive'}
                      </button>
                      <button type="button" className="danger" onClick={() => remove(product)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                )
              })}
              {visible.length === 0 && (
                <tr>
                  <td colSpan={7} className="empty-cell">
                    <Empty icon={Package} title={products.length === 0 ? 'No products yet' : 'No products match'}>
                      {products.length === 0 ? 'Add your first product to start building plans.' : 'Try another tab or search.'}
                    </Empty>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
