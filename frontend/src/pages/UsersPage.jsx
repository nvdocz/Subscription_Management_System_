import { useEffect, useState } from 'react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

const ROLES = ['admin', 'staff', 'customer']

export default function UsersPage() {
  const { user: currentUser } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .get('/auth/users/')
      .then(({ data }) => setUsers(data))
      .catch(() => setError('Could not load users.'))
      .finally(() => setLoading(false))
  }, [])

  const handleRoleChange = async (id, role) => {
    try {
      await api.patch(`/auth/users/${id}/role/`, { role })
      setUsers((prev) => prev.map((u) => (u.id === id ? { ...u, role } : u)))
    } catch {
      setError('Could not update role. Only admins can change roles.')
    }
  }

  if (loading) return <p className="status-message">Loading users...</p>

  return (
    <div>
      <h1>Users</h1>
      {error && <p className="form-error">{error}</p>}
      <table className="users-table">
        <thead>
          <tr>
            <th>Username</th>
            <th>Email</th>
            <th>Role</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.username}</td>
              <td>{u.email}</td>
              <td>
                {currentUser.role === 'admin' ? (
                  <select value={u.role} onChange={(e) => handleRoleChange(u.id, e.target.value)}>
                    {ROLES.map((role) => (
                      <option key={role} value={role}>
                        {role}
                      </option>
                    ))}
                  </select>
                ) : (
                  u.role
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
