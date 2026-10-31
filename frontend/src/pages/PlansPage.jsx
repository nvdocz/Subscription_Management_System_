import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Layers, Plus } from 'lucide-react'
import { activatePlan, deactivatePlan, deletePlan, listPlans, planAvailability } from '../api/plans'
import { useConfirm, useToast } from '../components/Toast'
import { Empty, FilterTabs, FREQUENCY_LABEL, PageHeader, Skeleton, StatusBadge, formatDate, money } from '../components/ui'
import './Catalog.css'

const AVAILABILITY = {
  available: { status: 'active', label: 'Available now' },
  scheduled: { status: 'scheduled', label: 'Not open yet' },
  ended: { status: 'expired', label: 'Ended' },
  inactive: { status: 'disabled', label: 'Switched off' },
}

const LIFECYCLE = [
  { key: 'auto_close_enabled', label: 'Auto-closes' },
  { key: 'allow_early_closure', label: 'Early closure' },
  { key: 'allow_pause', label: 'Pause' },
  { key: 'allow_renewal', label: 'Renewal' },
]

function window_(plan) {
  if (!plan.end_date) return `From ${formatDate(plan.start_date)}, open-ended`
  return `${formatDate(plan.start_date)} to ${formatDate(plan.end_date)}`
}

export default function PlansPage() {
  const toast = useToast()
  const confirm = useConfirm()
  const [plans, setPlans] = useState(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('all')

  const load = useCallback(() => {
    return listPlans()
      .then(setPlans)
      .catch(() => setError('Could not load plans.'))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const visible = useMemo(() => {
    const all = plans ?? []
    return tab === 'all' ? all : all.filter((p) => planAvailability(p) === tab)
  }, [plans, tab])

  const toggle = async (plan) => {
    try {
      const updated = plan.is_active ? await deactivatePlan(plan.id) : await activatePlan(plan.id)
      setPlans((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
      toast.success(`${plan.name} ${plan.is_active ? 'switched off' : 'switched on'}.`)
    } catch {
      toast.error('Could not change the plan.')
    }
  }

  const remove = async (plan) => {
    const ok = await confirm({
      title: `Delete the ${plan.name} plan?`,
      message: 'Subscriptions already on this plan are deleted with it. Switch the plan off instead to stop new sign-ups.',
      confirmLabel: 'Delete plan',
      tone: 'danger',
    })
    if (!ok) return
    try {
      await deletePlan(plan.id)
      setPlans((prev) => prev.filter((p) => p.id !== plan.id))
      toast.success('Plan deleted.')
    } catch {
      toast.error('Could not delete the plan.')
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Catalog"
        title="Plans"
        subtitle="What a product costs, how often it bills and which lifecycle options customers get."
        actions={
          <Link className="btn-primary" to="/plans/new">
            <Plus size={16} /> Create plan
          </Link>
        }
      />

      <div className="toolbar">
        <FilterTabs
          tabs={[
            { value: 'all', label: 'All', count: plans?.length },
            { value: 'available', label: 'Available now' },
            { value: 'scheduled', label: 'Upcoming' },
            { value: 'ended', label: 'Ended' },
            { value: 'inactive', label: 'Switched off' },
          ]}
          value={tab}
          onChange={setTab}
        />
      </div>

      {error && <p className="form-error">{error}</p>}

      {!plans ? (
        <div className="plan-grid">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} height={300} radius={14} />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <Empty icon={Layers} title={plans.length === 0 ? 'No plans yet' : 'No plans in this view'}>
          {plans.length === 0 ? 'Create a plan to make a product available to customers.' : 'Try another tab.'}
        </Empty>
      ) : (
        <div className="plan-grid">
          {visible.map((plan) => {
            const availability = AVAILABILITY[planAvailability(plan)]
            return (
              <article key={plan.id} className={`plan-card ${plan.is_active ? '' : 'is-off'}`}>
                <div className="plan-card-top">
                  <span className="plan-product">{plan.product_detail?.name}</span>
                  <StatusBadge status={availability.status} label={availability.label} />
                </div>
                <h2>{plan.name}</h2>
                <p className="plan-price">
                  {money(plan.price)} <span>/ {FREQUENCY_LABEL[plan.billing_frequency]}</span>
                </p>

                <dl className="plan-facts">
                  <dt>Minimum quantity</dt>
                  <dd>{plan.min_quantity}</dd>
                  <dt>Availability</dt>
                  <dd>{window_(plan)}</dd>
                </dl>

                <div className="chip-row">
                  {LIFECYCLE.map((option) => (
                    <span key={option.key} className={`chip ${plan[option.key] ? '' : 'off'}`}>
                      {option.label}
                    </span>
                  ))}
                </div>

                <div className="plan-actions">
                  <Link to={`/plans/${plan.id}/edit`}>Edit</Link>
                  <button type="button" onClick={() => toggle(plan)}>
                    {plan.is_active ? 'Switch off' : 'Switch on'}
                  </button>
                  <button type="button" className="danger" onClick={() => remove(plan)}>
                    Delete
                  </button>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
