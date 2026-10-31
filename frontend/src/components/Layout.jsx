import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import './Layout.css'

export default function Layout() {
  const { user, logout } = useAuth()

  return (
    <div className="layout">
      <header className="layout-header">
        <span className="brand">Subscription Manager</span>
        <nav>
          <NavLink to="/dashboard">Dashboard</NavLink>
          {(user?.role === 'admin' || user?.role === 'staff') && <NavLink to="/users">Users</NavLink>}
          {user?.role === 'admin' && <NavLink to="/products">Products</NavLink>}
        </nav>
        <div className="layout-user">
          <span>
            {user?.username} <span className="role-badge">{user?.role}</span>
          </span>
          <button type="button" onClick={logout}>
            Log out
          </button>
        </div>
      </header>
      <main className="layout-content">
        <Outlet />
      </main>
    </div>
  )
}
