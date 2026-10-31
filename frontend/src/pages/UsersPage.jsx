import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { UserPlus, Users } from 'lucide-react'
import api from '../api/client'
import { errorMessage } from '../api/subscriptions'
import { useToast } from '../components/Toast'
import { Avatar, Empty, FilterTabs, PageHeader, SearchInput, StatusBadge, TableSkeleton, formatDate } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import './Subscriptions.css'

const ROLES = ['admin', 'staff', 'customer']

export default function UsersPage() {
  const { user: currentUser } = useAuth()
  const toast = useToast()
  const isAdmin = currentUser.role === 'admin'
  const [users, setUsers] = useState(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('all')
  const [search, setSearch] = useState('')

  const refresh = useCallback(() => {
    api
      .get('/auth/users/')
      .then(({ data }) => setUsers(data))
      .catch(() => setError('Could not load users.'))
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const changeRole = async (id, role) => {
    try {
      await api.patch(`/auth/users/${id}/role/`, { role })
      setUsers((prev) => prev.map((u) => (u.id === id ? { ...u, role } : u)))
      toast.success('Role updated.')
    } catch (err) {
      toast.error(errorMessage(err, 'Only admins can change roles.'))
    }
  }

  const count = (role) => users?.filter((u) => u.role === role).length ?? 0
  const tabs = isAdmin
    ? [
        { value: 'all', label: 'Everyone', count: users?.length ?? 0 },
        { value: 'customer', label: 'Customers', count: count('customer') },
        { value: 'staff', label: 'Staff', count: count('staff') },
        { value: 'admin', label: 'Admins', count: count('admin') },
      ]
    : []

  const term = search.trim().toLowerCase()
  const visible = (users ?? []).filter(
    (u) => (tab === 'all' || u.role === tab) && (!term || `${u.username} ${u.email}`.toLowerCase().includes(term)),
  )

  return (
    <div>
      <PageHeader
        eyebrow={isAdmin ? 'People' : 'Sales'}
        title={isAdmin ? 'Users' : 'Customers'}
        subtitle={isAdmin ? 'Everyone with access to the system. Only admins can add staff or change roles.' : 'Customer accounts you can quote and subscribe.'}
        actions={
          <>
            {isAdmin && (
              <Link className="btn-secondary" to="/users/new?role=staff">
                <UserPlus size={16} /> Add staff
              </Link>
            )}
            <Link className="btn-primary" to="/users/new">
              <UserPlus size={16} /> Add customer
            </Link>
          </>
        }
      />

      <div className="toolbar">
        {isAdmin ? <FilterTabs tabs={tabs} value={tab} onChange={setTab} /> : <span />}
        <SearchInput value={search} onChange={setSearch} placeholder="Search name or email" />
      </div>

      {error && <p className="form-error">{error}</p>}

      {!users && !error ? (
        <TableSkeleton rows={6} cols={4} />
      ) : (
        users && (
          <div className="table-card">
            <table className="data-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Email</th>
                  <th>Joined</th>
                  <th>Role</th>
                  {!isAdmin && <th />}
                </tr>
              </thead>
              <tbody>
                {visible.map((u) => (
                  <tr key={u.id}>
                    <td>
                      <div className="cell-user">
                        <Avatar name={u.username} />
                        <span className="strong">{u.username}</span>
                      </div>
                    </td>
                    <td>{u.email}</td>
                    <td>{formatDate(u.date_joined)}</td>
                    <td>
                      {isAdmin ? (
                        <select
                          className="sort-select"
                          value={u.role}
                          onChange={(e) => changeRole(u.id, e.target.value)}
                          disabled={u.id === currentUser.id}
                          title={u.id === currentUser.id ? 'You cannot change your own role' : undefined}
                          aria-label={`Role for ${u.username}`}
                        >
                          {ROLES.map((role) => (
                            <option key={role} value={role}>
                              {role[0].toUpperCase() + role.slice(1)}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <StatusBadge status={u.role} />
                      )}
                    </td>
                    {!isAdmin && (
                      <td className="table-actions">
                        <Link to={`/subscriptions?customer=${u.id}`}>Subscriptions</Link>
                      </td>
                    )}
                  </tr>
                ))}
                {visible.length === 0 && (
                  <tr>
                    <td colSpan={isAdmin ? 4 : 5} className="empty-cell">
                      <Empty icon={Users} title="Nobody matches">
                        Try another name, email or role.
                      </Empty>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  )
}
