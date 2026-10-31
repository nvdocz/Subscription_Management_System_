import api from './client'

export const getInvoice = (id) => api.get(`/invoices/${id}/`).then((res) => res.data)
export const invoiceAction = (id, name) => api.post(`/invoices/${id}/${name}/`).then((res) => res.data)
export const confirmDrafts = () => api.post('/invoices/confirm-drafts/').then((res) => res.data)
export const listOpenInvoices = () =>
  api.get('/invoices/', { params: { status: 'confirmed', page_size: 100 } }).then((res) => res.data.results)

export const createPayment = (payload) => api.post('/payments/', payload).then((res) => res.data)

export const getBillingPreview = () => api.get('/billing/preview/').then((res) => res.data)
export const runBilling = (confirm) => api.post('/billing/run/', { confirm }).then((res) => res.data)

export const PAYMENT_METHODS = [
  { value: 'card', label: 'Card' },
  { value: 'bank_transfer', label: 'Bank transfer' },
  { value: 'upi', label: 'UPI' },
  { value: 'cash', label: 'Cash' },
  { value: 'cheque', label: 'Cheque' },
]
