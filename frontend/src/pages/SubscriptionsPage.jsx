import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Plus, Repeat, X } from 'lucide-react'
import { ACTION_LABELS, doSubscriptionAction, errorMessage } from '../api/subscriptions'
import { useToast } from '../components/Toast'
import {
  Empty,
  FilterTabs,
  FREQUENCY_LABEL,
  PageHeader,
  Pagination,
  SearchInput,
  StatusBadge,
  TableSkeleton,
  formatDate,
  money,
} from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useDebounced, usePaged } from '../hooks/usePaged'
import './Subscriptions.css'

const TABS = [
  { value: '', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'quotation', label: 'Quotation' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'active', label: 'Active' },
  { value: 'paused', label: 'Paused' },
  { value: 'closed', label: 'Closed' },
]

const SORTS = [
  { value: 'created', label: 'Newest first' },
  { value: 'next_billing', label: 'Next billing' },
  { value: 'expiry', label: 'Expiry date' },
  { value: 'start', label: 'Start date' },
  { value: 'number', label: 'Number' },
]

// Only actions that move a subscription forward get a shortcut in the list.
const QUICK_ACTIONS = ['send_quotation', 'confirm', 'activate', 'resume']

export default function SubscriptionsPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const isCustomer = user.role === 'customer'
  const customer = params.get('customer') ?? ''

  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [ordering, setOrdering] = useState('created')
  const [busyId, setBusyId] = useState(null)
  const q = useDebounced(search)

  const { rows, count, page, setPage, loading, error, reload, pageSize } = usePaged('/subscriptions/', {
    status,
    q,
    customer,
    ordering,
  })

  const quickAction = async (event, subscription, action) => {
    event.stopPropagation()
    setBusyId(subscription.id)
    try {
      await doSubscriptionAction(subscription.id, action)
      toast.success(`${subscription.number}: ${ACTION_LABELS[action].toLowerCase()} done.`)
      reload()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  const columns = isCustomer ? 8 : 9

  return (
    <div>
      <PageHeader
        eyebrow={isCustomer ? 'My account' : 'Sales'}
        title={isCustomer ? 'My subscriptions' : 'Subscriptions'}
        subtitle={
          isCustomer
            ? 'Every plan you are on, with its next billing date and recurring amount.'
            : 'Each subscription moves from draft to active. Open one to see exactly where it stands.'
        }
        actions={
          !isCustomer && (
            <Link className="btn-primary" to="/subscriptions/new">
              <Plus size={16} /> New subscription
            </Link>
          )
        }
      />

      <div className="toolbar">
        <FilterTabs tabs={isCustomer ? TABS.filter((t) => t.value !== 'draft') : TABS} value={status} onChange={setStatus} />
        <div className="toolbar-group">
          <select className="sort-select" value={ordering} onChange={(e) => setOrdering(e.target.value)} aria-label="Sort by">
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          <SearchInput value={search} onChange={setSearch} placeholder={isCustomer ? 'Search number or plan' : 'Search number, customer or plan'} />
        </div>
      </div>

      {customer && (
        <div className="filter-chip">
          Showing one customer&apos;s subscriptions
          <button type="button" onClick={() => setParams({})} aria-label="Clear customer filter">
            <X size={13} />
          </button>
        </div>
      )}

      {error && <p className="form-error">{error}</p>}

      {loading && rows.length === 0 ? (
        <TableSkeleton rows={8} cols={columns} />
      ) : (
        <div className={`table-card ${loading ? 'is-refreshing' : ''}`}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Subscription</th>
                {!isCustomer && <th>Customer</th>}
                <th>Plan</th>
                <th>Status</th>
                <th>Term</th>
                <th>Next billing</th>
                <th className="num">Recurring</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => {
                const quick = s.allowed_actions.find((a) => QUICK_ACTIONS.includes(a))
                return (
                  <tr key={s.id} className="row-link" onClick={() => navigate(`/subscriptions/${s.id}`)}>
                    <td className="doc">{s.number}</td>
                    {!isCustomer && <td className="strong">{s.customer_detail.username}</td>}
                    <td>
                      <div className="cell-stack">
                        <span className="strong">{s.plan_detail.name}</span>
                        <small>{s.plan_detail.product_name}</small>
                      </div>
                    </td>
                    <td>
                      <StatusBadge status={s.status} />
                    </td>
                    <td>
                      <div className="cell-stack">
                        <span>{formatDate(s.start_date)}</span>
                        <small>to {formatDate(s.expiry_date)}</small>
                      </div>
                    </td>
                    <td>{s.status === 'active' ? formatDate(s.next_billing_date) : '—'}</td>
                    <td className="num">
                      <div className="cell-stack end">
                        <span className="strong">{money(s.cycle_subtotal, 2)}</span>
                        <small>per {FREQUENCY_LABEL[s.plan_detail.billing_frequency]}</small>
                      </div>
                    </td>
                    <td className="table-actions">
                      {quick && (
                        <button type="button" disabled={busyId === s.id} onClick={(e) => quickAction(e, s, quick)}>
                          {ACTION_LABELS[quick]}
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={columns} className="empty-cell">
                    <Empty icon={Repeat} title="No subscriptions found">
                      {status || q || customer
                        ? 'Try a different status or search.'
                        : isCustomer
                          ? 'Browse plans to start your first subscription.'
                          : 'Create one, or convert an accepted quotation.'}
                    </Empty>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      <Pagination page={page} pageSize={pageSize} count={count} onPage={setPage} />
    </div>
  )
}
