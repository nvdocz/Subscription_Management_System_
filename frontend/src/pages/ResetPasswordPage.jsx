import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import api from '../api/client'
import { AuthShell, PASSWORD_RULES, PasswordRules } from '../components/AuthShell'
import { Field } from '../components/ui'

export default function ResetPasswordPage() {
  const { uid, token } = useParams()
  const navigate = useNavigate()
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const passwordOk = PASSWORD_RULES.every((rule) => rule.test(newPassword))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await api.post('/auth/password-reset/confirm/', { uid, token, new_password: newPassword })
      navigate('/login', { replace: true, state: { passwordReset: true } })
    } catch (err) {
      const data = err.response?.data
      setError(data?.new_password?.join(' ') ?? data?.detail ?? 'Could not reset the password.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthShell title="Choose a new password" subtitle="Use something you have not used here before." footer={<Link to="/login">Back to log in</Link>}>
      <form onSubmit={handleSubmit}>
        {error && <p className="form-error">{error}</p>}
        <Field label="New password">
          <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required autoFocus autoComplete="new-password" />
        </Field>
        <PasswordRules password={newPassword} />
        <button type="submit" className="btn-primary" disabled={submitting || !passwordOk}>
          {submitting ? 'Saving...' : 'Update password'}
        </button>
      </form>
    </AuthShell>
  )
}
