import api from './client'

export const listProducts = () => api.get('/products/').then((res) => res.data)
export const getProduct = (id) => api.get(`/products/${id}/`).then((res) => res.data)
export const createProduct = (payload) => api.post('/products/', payload).then((res) => res.data)
export const updateProduct = (id, payload) => api.patch(`/products/${id}/`, payload).then((res) => res.data)
export const deleteProduct = (id) => api.delete(`/products/${id}/`)
export const archiveProduct = (id) => api.post(`/products/${id}/archive/`).then((res) => res.data)
export const unarchiveProduct = (id) => api.post(`/products/${id}/unarchive/`).then((res) => res.data)

export const addVariant = (productId, payload) =>
  api.post(`/products/${productId}/variants/`, payload).then((res) => res.data)
export const deleteVariant = (productId, variantId) => api.delete(`/products/${productId}/variants/${variantId}/`)
