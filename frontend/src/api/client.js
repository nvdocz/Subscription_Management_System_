import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

export const ACCESS_TOKEN_KEY = 'access_token'
export const REFRESH_TOKEN_KEY = 'refresh_token'

const api = axios.create({ baseURL: API_BASE_URL })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let refreshPromise = null

async function refreshAccessToken() {
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)
  if (!refreshToken) {
    throw new Error('No refresh token available')
  }
  const { data } = await axios.post(`${API_BASE_URL}/auth/login/refresh/`, { refresh: refreshToken })
  localStorage.setItem(ACCESS_TOKEN_KEY, data.access)
  return data.access
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error
    if (response && response.status === 401 && !config._retried) {
      config._retried = true
      try {
        refreshPromise = refreshPromise || refreshAccessToken()
        const newAccessToken = await refreshPromise
        refreshPromise = null
        config.headers.Authorization = `Bearer ${newAccessToken}`
        return api(config)
      } catch {
        refreshPromise = null
        localStorage.removeItem(ACCESS_TOKEN_KEY)
        localStorage.removeItem(REFRESH_TOKEN_KEY)
      }
    }
    return Promise.reject(error)
  },
)

export default api
