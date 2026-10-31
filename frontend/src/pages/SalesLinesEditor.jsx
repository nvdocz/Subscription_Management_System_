import { Plus, Trash2 } from 'lucide-react'
import { emptyLine, unitPriceFor } from '../api/subscriptions'
import { money } from '../components/ui'
import './Quotations.css'

/**
 * Product lines for subscriptions, quotations and templates.
 * taxMode "auto": a blank tax % means the admin tax rules decide at billing time.
 * taxMode "fill": picking a product fills its default tax rate into the field.
 */
export default function SalesLinesEditor({ lines, onChange, products, taxMode = 'auto', minQuantity = 1 }) {
  const update = (index, patch) => onChange(lines.map((line, i) => (i === index ? { ...line, ...patch } : line)))

  const pickProduct = (index, productId) => {
    const product = products.find((p) => String(p.id) === String(productId))
    update(index, {
      product: productId,
      variant: '',
      unit_price: unitPriceFor(product, ''),
      tax_rate: taxMode === 'fill' && product ? String(product.default_tax_rate ?? 0) : '',
    })
  }

  const pickVariant = (index, variantId) => {
    const product = products.find((p) => String(p.id) === String(lines[index].product))
    update(index, { variant: variantId, unit_price: unitPriceFor(product, variantId) })
  }

  return (
    <div className="lines-editor">
      <div className="table-card">
        <table className="data-table lines-table">
          <thead>
            <tr>
              <th>Product</th>
              <th>Variant</th>
              <th className="num">Qty</th>
              <th className="num">Unit price</th>
              <th className="num">Tax %</th>
              <th className="num">Amount</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {lines.map((line, index) => {
              const product = products.find((p) => String(p.id) === String(line.product))
              const amount = Number(line.quantity || 0) * Number(line.unit_price || 0)
              return (
                <tr key={index}>
                  <td className="cell-product">
                    <select value={line.product} onChange={(e) => pickProduct(index, e.target.value)} required aria-label="Product">
                      <option value="">Select a product</option>
                      {products.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="cell-variant">
                    <select
                      value={line.variant}
                      onChange={(e) => pickVariant(index, e.target.value)}
                      disabled={!product?.variants?.length}
                      aria-label="Variant"
                    >
                      <option value="">{product?.variants?.length ? 'Standard' : 'None'}</option>
                      {product?.variants?.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.name} (+{money(v.extra_price)})
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="cell-narrow">
                    <input
                      type="number"
                      min={minQuantity}
                      value={line.quantity}
                      onChange={(e) => update(index, { quantity: e.target.value })}
                      required
                      aria-label="Quantity"
                    />
                  </td>
                  <td className="cell-price">
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={line.unit_price}
                      onChange={(e) => update(index, { unit_price: e.target.value })}
                      required
                      aria-label="Unit price"
                    />
                  </td>
                  <td className="cell-narrow">
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      max="100"
                      value={line.tax_rate}
                      placeholder={product ? `Auto ${Number(product.default_tax_rate ?? 0)}` : 'Auto'}
                      onChange={(e) => update(index, { tax_rate: e.target.value })}
                      aria-label="Tax percent"
                    />
                  </td>
                  <td className="num strong">{money(amount, 2)}</td>
                  <td className="table-actions">
                    {lines.length > 1 && (
                      <button type="button" className="icon-btn" onClick={() => onChange(lines.filter((_, i) => i !== index))} aria-label="Remove line">
                        <Trash2 size={15} />
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn-secondary btn-small" onClick={() => onChange([...lines, emptyLine(minQuantity)])}>
        <Plus size={14} /> Add line
      </button>
    </div>
  )
}
