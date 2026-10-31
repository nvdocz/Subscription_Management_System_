import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import api from '../api/client'
import { errorMessage } from '../api/subscriptions'
import { PASSWORD_RULES, PasswordRules } from '../components/AuthShell'
import { useToast } from '../components/Toast'
import { Field, PageHeader } from '../components/ui'
import { useAuth } from '../context/AuthContext'

export default function AddUserPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const [params] = useSearchParams()
  const isAdmin = user.role === 'admin'
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    role: isAdmin && params.get('role') === 'staff' ? 'staff' : 'customer',
  })
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value })
  const passwordOk = PASSWORD_RULES.every((rule) => rule.test(form.password))
  const noun = form.role === 'staff' ? 'staff member' : 'customer'

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrors({})
    setSubmitting(true)
    try {
      await api.post('/auth/users/', form)
      toast.success(`${form.username} was added as a ${noun}.`)
      navigate('/users')
    } catch (err) {
      const data = err.response?.data
      setErrors(data && typeof data === 'object' && !Array.isArray(data) ? data : { detail: errorMessage(err) })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow={isAdmin ? 'People' : 'Sales'}
        title={`Add ${noun}`}
        subtitle="Create the account now and share the temporary password with them. They can reset it any time."
      />
      <form className="form-card" onSubmit={handleSubmit}>
        {errors.detail && <p className="form-error">{errors.detail}</p>}
        {isAdmin && (
          <Field label="Role" error={errors.role} hint="Only admins can add staff.">
            <select value={form.role} onChange={set('role')}>
              <option value="customer">Customer</option>
              <option value="staff">Staff</option>
            </select>
          </Field>
        )}
        {!isAdmin && errors.role && <p className="form-error">{[].concat(errors.role).join(' ')}</p>}
        <Field label="Username" error={errors.username}>
          <input value={form.username} onChange={set('username')} required autoFocus autoComplete="off" />
        </Field>
        <Field label="Email" error={errors.email} hint="Each email can belong to only one account.">
          <input type="email" value={form.email} onChange={set('email')} required autoComplete="off" />
        </Field>
        <Field label="Temporary password" error={errors.password}>
          <input type="password" value={form.password} onChange={set('password')} required autoComplete="new-password" />
        </Field>
        <PasswordRules password={form.password} />
        <div className="form-actions">
          <button type="submit" disabled={submitting || !passwordOk}>
            {submitting ? 'Creating...' : `Create ${noun}`}
          </button>
          <Link className="btn-ghost" to="/users">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  )
}
