import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import api, { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const loadUser = useCallback(async () => {
    if (!localStorage.getItem(ACCESS_TOKEN_KEY)) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      const { data } = await api.get('/auth/me/')
      setUser(data)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadUser()
  }, [loadUser])

  const login = async (username, password) => {
    const { data } = await api.post('/auth/login/', { username, password })
    localStorage.setItem(ACCESS_TOKEN_KEY, data.access)
    localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh)
    await loadUser()
  }

  const register = async (username, email, password) => {
    await api.post('/auth/register/', { username, email, password })
  }

  const logout = () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
