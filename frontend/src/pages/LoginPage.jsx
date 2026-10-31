import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { AuthShell } from '../components/AuthShell'
import { Field } from '../components/ui'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const notice = location.state?.registered
    ? 'Your account is ready. Log in to continue.'
    : location.state?.passwordReset
      ? 'Password updated. Log in with your new password.'
      : ''

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(form.username, form.password)
      navigate(location.state?.from ?? '/dashboard', { replace: true })
    } catch {
      setError('That username and password do not match.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Log in to manage subscriptions, invoices and payments."
      footer={
        <span>
          New to Brightloop? <Link to="/register">Create an account</Link>
        </span>
      }
    >
      <form onSubmit={handleSubmit}>
        {notice && <p className="form-success">{notice}</p>}
        {error && <p className="form-error">{error}</p>}
        <Field label="Username">
          <input name="username" value={form.username} onChange={handleChange} required autoFocus autoComplete="username" />
        </Field>
        <Field label="Password">
          <input type="password" name="password" value={form.password} onChange={handleChange} required autoComplete="current-password" />
        </Field>
        <p className="auth-links">
          <Link to="/forgot-password">Forgot your password?</Link>
        </p>
        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? 'Logging in...' : 'Log in'}
        </button>
      </form>
    </AuthShell>
  )
}
