import { useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'
import { AuthShell } from '../components/AuthShell'
import { Field } from '../components/ui'

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
    <AuthShell
      title="Reset your password"
      subtitle="Enter your registered email and we will send you a reset link."
      footer={<Link to="/login">Back to log in</Link>}
    >
      <form onSubmit={handleSubmit}>
        {message && <p className="form-success">{message}</p>}
        <Field label="Email">
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
        </Field>
        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? 'Sending...' : 'Send reset link'}
        </button>
      </form>
    </AuthShell>
  )
}
