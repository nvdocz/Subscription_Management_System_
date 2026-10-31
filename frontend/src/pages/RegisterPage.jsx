import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import './AuthForms.css'

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', email: '', password: '' })
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

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

  const fieldError = (field) => {
    const value = errors[field]
    if (!value) return null
    return Array.isArray(value) ? value.join(' ') : value
  }

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>Create an account</h1>
        {errors.detail && <p className="form-error">{errors.detail}</p>}
        <label>
          Username
          <input name="username" value={form.username} onChange={handleChange} required autoFocus />
          {fieldError('username') && <span className="field-error">{fieldError('username')}</span>}
        </label>
        <label>
          Email
          <input type="email" name="email" value={form.email} onChange={handleChange} required />
          {fieldError('email') && <span className="field-error">{fieldError('email')}</span>}
        </label>
        <label>
          Password
          <input type="password" name="password" value={form.password} onChange={handleChange} required />
          {fieldError('password') && <span className="field-error">{fieldError('password')}</span>}
        </label>
        <button type="submit" disabled={submitting}>
          {submitting ? 'Creating account...' : 'Register'}
        </button>
        <p className="auth-links">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </div>
  )
}
