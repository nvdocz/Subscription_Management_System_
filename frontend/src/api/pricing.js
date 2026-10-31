import api from './client'

export const listTaxRules = () => api.get('/tax-rules/').then((res) => res.data)
export const createTaxRule = (payload) => api.post('/tax-rules/', payload).then((res) => res.data)
export const updateTaxRule = (id, payload) => api.patch(`/tax-rules/${id}/`, payload).then((res) => res.data)
export const deleteTaxRule = (id) => api.delete(`/tax-rules/${id}/`)

export const listDiscounts = () => api.get('/discounts/').then((res) => res.data)
export const createDiscount = (payload) => api.post('/discounts/', payload).then((res) => res.data)
export const updateDiscount = (id, payload) => api.patch(`/discounts/${id}/`, payload).then((res) => res.data)
export const deleteDiscount = (id) => api.delete(`/discounts/${id}/`)

export const listSellableProducts = () => api.get('/catalog/products/').then((res) => res.data)
