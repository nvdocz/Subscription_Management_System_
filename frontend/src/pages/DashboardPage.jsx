import { useAuth } from '../context/AuthContext'

const COPY = {
  admin: 'Full system control: manage staff, customers, subscriptions and invoices.',
  staff: 'Manage customers, subscriptions and invoices.',
  customer: 'View and manage your own subscriptions.',
}

export default function DashboardPage() {
  const { user } = useAuth()

  return (
    <div>
      <h1>Welcome, {user.username}</h1>
      <p>{COPY[user.role] ?? 'Welcome to your dashboard.'}</p>
    </div>
  )
}
