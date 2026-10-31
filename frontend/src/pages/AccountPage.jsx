import { Link } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { PageHeader, Panel, StatusBadge, formatDate, Avatar } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import './Quotations.css'
import './Subscriptions.css'

export default function AccountPage() {
  const { user, logout } = useAuth()

  return (
    <div>
      <PageHeader eyebrow="My account" title="Profile and security" subtitle="Your details and how to keep your account safe." />
      <div className="panel-grid">
        <Panel title="Profile">
          <div className="profile-head">
            <Avatar name={user.username} size={48} />
            <div>
              <h3>{user.username}</h3>
              <span>{user.email}</span>
            </div>
          </div>
          <dl className="facts">
            <div>
              <dt>Role</dt>
              <dd>
                <StatusBadge status={user.role} />
              </dd>
            </div>
            <div>
              <dt>Member since</dt>
              <dd>{formatDate(user.date_joined)}</dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>{user.email}</dd>
            </div>
          </dl>
        </Panel>

        <Panel title="Security">
          <p className="security-copy">
            To change your password, we email a secure link to {user.email}. It stays valid for a short time and works once.
          </p>
          <div className="page-actions">
            <Link className="btn-primary" to="/forgot-password" onClick={logout}>
              Send password reset link
            </Link>
            <button type="button" className="btn-secondary" onClick={logout}>
              <LogOut size={15} /> Log out
            </button>
          </div>
        </Panel>
      </div>
    </div>
  )
}
