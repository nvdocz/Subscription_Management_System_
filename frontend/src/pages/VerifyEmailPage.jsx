import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import api from '../api/client'
import { AuthShell } from '../components/AuthShell'

export default function VerifyEmailPage() {
  const { uid, token } = useParams()
  const [state, setState] = useState({ status: 'working', message: '' })

  useEffect(() => {
    let cancelled = false
    api
      .post('/auth/verify-email/', { uid, token })
      .then(({ data }) => !cancelled && setState({ status: 'done', message: data.detail }))
      .catch((err) => !cancelled && setState({ status: 'failed', message: err.response?.data?.detail ?? 'Could not confirm your email.' }))
    return () => {
      cancelled = true
    }
  }, [uid, token])

  return (
    <AuthShell
      title={state.status === 'done' ? 'Email confirmed' : state.status === 'failed' ? 'Link not valid' : 'Confirming your email'}
      subtitle="Brightloop Billing"
      footer={<Link to="/login">Go to log in</Link>}
    >
      {state.status === 'working' && <p>One moment...</p>}
      {state.status === 'done' && <p className="form-success">{state.message}</p>}
      {state.status === 'failed' && <p className="form-error">{state.message} Log in to request a new link.</p>}
    </AuthShell>
  )
}
