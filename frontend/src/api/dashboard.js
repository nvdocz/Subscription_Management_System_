import api from './client'

export const getDashboard = (role) => api.get(`/dashboard/${role}/`).then((res) => res.data)

export const getReports = (filters = {}) => {
  const params = {}
  if (filters.from) params.from = filters.from
  if (filters.to) params.to = filters.to
  if (filters.plan) params.plan = filters.plan
  return api.get('/dashboard/reports/', { params }).then((res) => res.data)
}
