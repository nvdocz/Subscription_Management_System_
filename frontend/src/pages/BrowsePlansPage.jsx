import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BadgeCheck } from 'lucide-react'
import api from '../api/client'
import { errorMessage } from '../api/subscriptions'
import { useConfirm, useToast } from '../components/Toast'
import { Empty, FREQUENCY_LABEL, PageHeader, Skeleton, money } from '../components/ui'

function PlanAction({ plan, busy, onRequest }) {
  if (plan.relation === 'current') {
    return (
      <button type="button" className="btn-secondary" disabled>
        Your current plan
      </button>
    )
  }
  if (plan.relation === 'downgrade') {
    return (
      <button type="button" className="btn-secondary btn-small" disabled title="Contact our team to move to a lower plan">
        Downgrade
      </button>
    )
  }
  if (plan.requested) {
    return (
      <button type="button" className="btn-secondary" disabled>
        Request pending
      </button>
    )
  }
  const label = plan.relation === 'upgrade' ? 'Upgrade' : 'Subscribe'
  return (
    <button type="button" className="btn-primary" disabled={busy} onClick={() => onRequest(plan, label)}>
      {busy ? 'Sending...' : label}
    </button>
  )
}

export default function BrowsePlansPage() {
  const toast = useToast()
  const confirm = useConfirm()
  const [plans, setPlans] = useState(null)
  const [error, setError] = useState('')
  const [requested, setRequested] = useState(false)
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(
    () =>
      api
        .get('/catalog/plans/')
        .then((res) => setPlans(res.data))
        .catch(() => setError('Could not load plans.')),
    [],
  )

  useEffect(() => {
    load()
  }, [load])

  const handleRequest = async (plan, label) => {
    const ok = await confirm({
      title: `${label} to ${plan.name}?`,
      message: "We'll send you a quotation to review. Nothing changes until you accept it.",
      confirmLabel: `Request ${label.toLowerCase()}`,
    })
    if (!ok) return
    setError('')
    setBusyId(plan.id)
    try {
      await api.post(`/catalog/plans/${plan.id}/request/`)
      toast.success(`Quotation requested for ${plan.name}.`)
      setRequested(true)
      await load()
    } catch (err) {
      setError(errorMessage(err, 'Could not send your request.'))
    } finally {
      setBusyId(null)
    }
  }

  const hasSubscription = plans?.some((p) => p.relation === 'current')

  return (
    <div>
      <PageHeader
        eyebrow="Customer portal"
        title="Browse plans"
        subtitle={hasSubscription ? 'Your current plan is marked. Upgrade whenever you outgrow it.' : 'Pick the plan that fits and request a quotation.'}
      />
      {error && (
        <p className="form-error" style={{ marginBottom: 16 }}>
          {error}
        </p>
      )}
      {requested && (
        <p className="form-success" style={{ marginBottom: 16 }}>
          Request sent. Review and accept it under <Link to="/quotations">My quotations</Link>.
        </p>
      )}
      {!plans && !error && (
        <div className="catalog-grid">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} height={320} radius={14} />
          ))}
        </div>
      )}
      {plans && plans.length === 0 && (
        <Empty title="No plans available right now">New plans will appear here as soon as they open.</Empty>
      )}
      {plans && (
        <div className="catalog-grid">
          {plans.map((p) => (
            <div key={p.id} className={`catalog-card ${p.relation === 'current' ? 'current' : ''}`}>
              <div className="catalog-top">
                <span className="product">{p.product_name}</span>
                {p.relation === 'current' && (
                  <span className="catalog-tag">
                    <BadgeCheck size={14} /> Currently using
                  </span>
                )}
              </div>
              <h2>{p.name}</h2>
              <p className="price">
                {money(p.price)} <span>/ {FREQUENCY_LABEL[p.billing_frequency]}</span>
              </p>
              {p.product_description && <p className="list-meta">{p.product_description}</p>}
              <ul>
                <li>Minimum quantity: {p.min_quantity}</li>
                <li>{p.allow_pause ? 'Pause whenever you need' : 'Cannot be paused'}</li>
                <li>{p.allow_early_closure ? 'Close early if plans change' : 'Runs to its expiry date'}</li>
                <li>{p.allow_renewal ? 'Renew when it ends' : 'Not renewable'}</li>
              </ul>
              <div className="catalog-actions">
                <PlanAction plan={p} busy={busyId === p.id} onRequest={handleRequest} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
