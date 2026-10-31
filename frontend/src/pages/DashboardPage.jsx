import { useEffect, useState } from 'react'
import { getDashboard } from '../api/dashboard'
import { PageHeader, PageSkeleton } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import AdminDashboard from './dashboards/AdminDashboard'
import CustomerDashboard from './dashboards/CustomerDashboard'
import StaffDashboard from './dashboards/StaffDashboard'
import './dashboards/dashboards.css'

const VIEWS = { admin: AdminDashboard, staff: StaffDashboard, customer: CustomerDashboard }

const COPY = {
  admin: { eyebrow: 'Administrator', subtitle: 'The whole business at a glance: revenue, receivables and growth.' },
  staff: { eyebrow: 'Operations', subtitle: 'What needs doing today across quotations, billing and collections.' },
  customer: { eyebrow: 'Customer portal', subtitle: 'Your subscription, what is due and what you have paid.' },
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const View = VIEWS[user.role]
  const copy = COPY[user.role]
  const today = new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })

  useEffect(() => {
    let active = true
    getDashboard(user.role)
      .then((payload) => active && setData(payload))
      .catch(() => active && setError(true))
    return () => {
      active = false
    }
  }, [user.role, attempt])

  const retry = () => {
    setError(false)
    setData(null)
    setAttempt((n) => n + 1)
  }

  return (
    <div>
      <PageHeader eyebrow={`${copy.eyebrow} · ${today}`} title={`Welcome back, ${user.username}`} subtitle={copy.subtitle} />
      {error && (
        <div className="error-panel">
          <p className="form-error">We could not load your dashboard. Check your connection and try again.</p>
          <button type="button" className="btn-secondary" onClick={retry}>
            Try again
          </button>
        </div>
      )}
      {!data && !error && <PageSkeleton />}
      {data && <View data={data} />}
    </div>
  )
}
