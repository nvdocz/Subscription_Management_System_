import api from './client'

export const listQuotations = () => api.get('/quotations/').then((res) => res.data)
export const getQuotation = (id) => api.get(`/quotations/${id}/`).then((res) => res.data)
export const createQuotation = (payload) => api.post('/quotations/', payload).then((res) => res.data)
export const updateQuotation = (id, payload) => api.patch(`/quotations/${id}/`, payload).then((res) => res.data)
export const deleteQuotation = (id) => api.delete(`/quotations/${id}/`)
export const sendQuotation = (id) => api.post(`/quotations/${id}/send/`).then((res) => res.data)
export const acceptQuotation = (id) => api.post(`/quotations/${id}/accept/`).then((res) => res.data)
export const rejectQuotation = (id) => api.post(`/quotations/${id}/reject/`).then((res) => res.data)
export const convertQuotation = (id) => api.post(`/quotations/${id}/convert/`).then((res) => res.data)

export const listTemplates = () => api.get('/quotation-templates/').then((res) => res.data)
export const getTemplate = (id) => api.get(`/quotation-templates/${id}/`).then((res) => res.data)
export const createTemplate = (payload) => api.post('/quotation-templates/', payload).then((res) => res.data)
export const deleteTemplate = (id) => api.delete(`/quotation-templates/${id}/`)

/** Form lines -> API items. Quotation items need a concrete tax rate, so a blank one falls back to the product default. */
export function toItems(lines, products) {
  return lines.map((line) => {
    const product = products.find((p) => String(p.id) === String(line.product))
    return {
      product: line.product,
      variant: line.variant || null,
      quantity: line.quantity,
      unit_price: line.unit_price,
      tax_rate: line.tax_rate === '' ? (product?.default_tax_rate ?? 0) : line.tax_rate,
    }
  })
}

export const fromItems = (items) =>
  items.map((item) => ({
    product: item.product,
    variant: item.variant ?? '',
    quantity: item.quantity,
    unit_price: item.unit_price,
    tax_rate: String(item.tax_rate ?? ''),
  }))
