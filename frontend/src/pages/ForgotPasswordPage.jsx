import { useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'
import './AuthForms.css'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      const { data } = await api.post('/auth/password-reset/', { email })
      setMessage(data.detail)
    } catch {
      setMessage('Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>Forgot password</h1>
        <p className="auth-copy">Enter your email and we&apos;ll send you a link to reset your password.</p>
        {message && <p className="form-success">{message}</p>}
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
        </label>
        <button type="submit" disabled={submitting}>
          {submitting ? 'Sending...' : 'Send reset link'}
        </button>
        <p className="auth-links">
          <Link to="/login">Back to login</Link>
        </p>
      </form>
    </div>
  )
}
