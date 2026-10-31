import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import api from '../api/client'
import './AuthForms.css'

export default function ResetPasswordPage() {
  const { uid, token } = useParams()
  const navigate = useNavigate()
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await api.post('/auth/password-reset/confirm/', { uid, token, new_password: newPassword })
      navigate('/login', { replace: true, state: { passwordReset: true } })
    } catch (err) {
      const data = err.response?.data
      setError(data?.new_password?.join(' ') ?? data?.detail ?? 'Could not reset password.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>Reset password</h1>
        {error && <p className="form-error">{error}</p>}
        <label>
          New password
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            autoFocus
          />
        </label>
        <button type="submit" disabled={submitting}>
          {submitting ? 'Resetting...' : 'Reset password'}
        </button>
        <p className="auth-links">
          <Link to="/login">Back to login</Link>
        </p>
      </form>
    </div>
  )
}
