import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { LogOut, Search } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { NAV_GROUPS, flatNav } from '../nav'
import { BrandMark, Wordmark } from './Brand'
import CommandPalette from './CommandPalette'
import { Avatar, StatusBadge } from './ui'
import './Layout.css'

function usePageTitle(role) {
  const { pathname } = useLocation()
  const match = flatNav(role)
    .filter((item) => pathname === item.to || pathname.startsWith(`${item.to}/`))
    .sort((a, b) => b.to.length - a.to.length)[0]
  return match?.label ?? 'Brightloop'
}

export default function Layout() {
  const { user, logout } = useAuth()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const groups = NAV_GROUPS[user?.role] ?? NAV_GROUPS.customer
  const title = usePageTitle(user?.role)
  const today = new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })

  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((open) => !open)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <BrandMark />
          <Wordmark light />
        </div>

        <nav className="sidebar-nav">
          {groups.map((group) => (
            <div key={group.label} className="nav-group">
              <span className="nav-group-label">{group.label}</span>
              {group.items.map(({ to, label, icon: Icon }) => (
                <NavLink key={to} to={to} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                  <Icon size={17} />
                  <span>{label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-user">
          <Avatar name={user?.username} size={34} />
          <div className="sidebar-user-info">
            <span className="sidebar-user-name">{user?.username}</span>
            <StatusBadge status={user?.role} />
          </div>
          <button type="button" className="logout-btn" onClick={logout} title="Log out" aria-label="Log out">
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      <div className="shell-main">
        <header className="topbar">
          <div className="topbar-title">
            <span>{today}</span>
            <strong>{title}</strong>
          </div>
          <button type="button" className="search-trigger" onClick={() => setPaletteOpen(true)}>
            <Search size={15} />
            <span>Search or jump to</span>
            <kbd>Ctrl K</kbd>
          </button>
        </header>
        <main className="shell-content">
          <div className="shell-inner">
            <Outlet />
          </div>
        </main>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} role={user?.role} />
    </div>
  )
}
