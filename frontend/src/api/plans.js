import api from './client'

export const listPlans = () => api.get('/plans/').then((res) => res.data)
export const getPlan = (id) => api.get(`/plans/${id}/`).then((res) => res.data)
export const createPlan = (payload) => api.post('/plans/', payload).then((res) => res.data)
export const updatePlan = (id, payload) => api.patch(`/plans/${id}/`, payload).then((res) => res.data)
export const deletePlan = (id) => api.delete(`/plans/${id}/`)
export const activatePlan = (id) => api.post(`/plans/${id}/activate/`).then((res) => res.data)
export const deactivatePlan = (id) => api.post(`/plans/${id}/deactivate/`).then((res) => res.data)

export const FREQUENCIES = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly' },
  { value: 'yearly', label: 'Yearly' },
]

/** Where a plan sits in its availability window: available, scheduled, ended or inactive. */
export function planAvailability(plan, today = new Date().toISOString().slice(0, 10)) {
  if (!plan.is_active) return 'inactive'
  if (plan.start_date > today) return 'scheduled'
  if (plan.end_date && plan.end_date < today) return 'ended'
  return 'available'
}
