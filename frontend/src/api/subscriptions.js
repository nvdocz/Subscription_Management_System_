import api from './client'

export const getSubscription = (id) => api.get(`/subscriptions/${id}/`).then((res) => res.data)
export const createSubscription = (payload) => api.post('/subscriptions/', payload).then((res) => res.data)
export const updateSubscription = (id, payload) => api.patch(`/subscriptions/${id}/`, payload).then((res) => res.data)
export const doSubscriptionAction = (id, action) => api.post(`/subscriptions/${id}/do/${action}/`).then((res) => res.data)

export const loadCustomers = () =>
  api.get('/auth/users/').then((res) => res.data.filter((user) => user.role === 'customer'))
export const loadPlanOptions = () => api.get('/catalog/plans/').then((res) => res.data)
export const loadProductOptions = () => api.get('/catalog/products/').then((res) => res.data)

export const emptyLine = (quantity = 1) => ({ product: '', variant: '', quantity, unit_price: '', tax_rate: '' })

export const STEPS = [
  { value: 'draft', label: 'Draft' },
  { value: 'quotation', label: 'Quotation' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'active', label: 'Active' },
  { value: 'closed', label: 'Closed' },
]

export const ACTION_LABELS = {
  send_quotation: 'Send quotation',
  confirm: 'Confirm',
  activate: 'Activate',
  pause: 'Pause',
  resume: 'Resume',
  close: 'Close',
  renew: 'Renew',
}

export const PAYMENT_TERMS = [
  { value: 'immediate', label: 'Immediate payment' },
  { value: 'net_15', label: 'Net 15 days' },
  { value: 'net_30', label: 'Net 30 days' },
  { value: 'net_45', label: 'Net 45 days' },
]

export const paymentTermsLabel = (value) => PAYMENT_TERMS.find((t) => t.value === value)?.label ?? value

function flatten(value) {
  if (Array.isArray(value)) return value.map(flatten).filter(Boolean).join(' ')
  if (value && typeof value === 'object') return Object.values(value).map(flatten).filter(Boolean).join(' ')
  return value ? String(value) : ''
}

export function errorMessage(err, fallback = 'Something went wrong. Please try again.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (Array.isArray(data)) return flatten(data) || fallback
  if (data.detail) return data.detail
  const parts = Object.entries(data).map(([key, value]) => `${key.replace(/_/g, ' ')}: ${flatten(value)}`)
  return parts.join('. ') || fallback
}

/** Line prices: variant extra price is added on top of the product's sales price. */
export function unitPriceFor(product, variantId) {
  if (!product) return ''
  const variant = product.variants?.find((v) => String(v.id) === String(variantId))
  return (Number(product.sales_price) + Number(variant?.extra_price ?? 0)).toFixed(2)
}

/** Totals for a lines editor. A blank tax rate means "automatic", which uses the product's default rate. */
export function computeTotals(lines, products) {
  let subtotal = 0
  let tax = 0
  for (const line of lines) {
    const product = products.find((p) => String(p.id) === String(line.product))
    const amount = Number(line.quantity || 0) * Number(line.unit_price || 0)
    const rate = line.tax_rate !== '' && line.tax_rate != null ? Number(line.tax_rate) : Number(product?.default_tax_rate ?? 0)
    subtotal += amount
    tax += (amount * rate) / 100
  }
  return { subtotal, tax, total: subtotal + tax }
}
