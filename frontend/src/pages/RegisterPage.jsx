import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthShell, PASSWORD_RULES, PasswordRules } from '../components/AuthShell'
import { Field } from '../components/ui'
import { useAuth } from '../context/AuthContext'

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', email: '', password: '' })
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })
  const passwordOk = PASSWORD_RULES.every((rule) => rule.test(form.password))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrors({})
    setSubmitting(true)
    try {
      await register(form.username, form.email, form.password)
      navigate('/login', { replace: true, state: { registered: true } })
    } catch (err) {
      setErrors(err.response?.data ?? { detail: 'Registration failed.' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="Manage your subscriptions, invoices and payments in one place."
      footer={
        <span>
          Already registered? <Link to="/login">Log in</Link>
        </span>
      }
    >
      <form onSubmit={handleSubmit}>
        {errors.detail && <p className="form-error">{errors.detail}</p>}
        <Field label="Username" error={errors.username}>
          <input name="username" value={form.username} onChange={handleChange} required autoFocus autoComplete="username" />
        </Field>
        <Field label="Email" error={errors.email} hint="One account per email address.">
          <input type="email" name="email" value={form.email} onChange={handleChange} required autoComplete="email" />
        </Field>
        <Field label="Password" error={errors.password}>
          <input type="password" name="password" value={form.password} onChange={handleChange} required autoComplete="new-password" />
        </Field>
        <PasswordRules password={form.password} />
        <button type="submit" className="btn-primary" disabled={submitting || !passwordOk}>
          {submitting ? 'Creating account...' : 'Create account'}
        </button>
      </form>
    </AuthShell>
  )
}
