import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Plus } from 'lucide-react'
import {
  acceptQuotation,
  convertQuotation,
  deleteQuotation,
  listQuotations,
  rejectQuotation,
  sendQuotation,
} from '../api/quotations'
import { errorMessage } from '../api/subscriptions'
import { useConfirm, useToast } from '../components/Toast'
import {
  Empty,
  FilterTabs,
  PageHeader,
  SearchInput,
  StatusBadge,
  TableSkeleton,
  daysFromToday,
  formatDate,
  money,
} from '../components/ui'
import { useAuth } from '../context/AuthContext'
import './Quotations.css'

const STATUSES = ['draft', 'sent', 'accepted', 'rejected', 'expired']

export default function QuotationsPage() {
  const { user } = useAuth()
  const toast = useToast()
  const confirm = useConfirm()
  const isCustomer = user.role === 'customer'

  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('all')
  const [search, setSearch] = useState('')
  const [busyId, setBusyId] = useState(null)

  const refresh = useCallback(() => {
    listQuotations()
      .then(setRows)
      .catch(() => setError('Could not load quotations.'))
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const counts = useMemo(() => {
    const result = { all: rows?.length ?? 0 }
    STATUSES.forEach((s) => (result[s] = rows?.filter((q) => q.status === s).length ?? 0))
    return result
  }, [rows])

  const tabs = [{ value: 'all', label: 'All', count: counts.all }].concat(
    STATUSES.filter((s) => counts[s] > 0 || (!isCustomer && s === 'draft') || s === 'sent').map((s) => ({
      value: s,
      label: s === 'sent' ? 'Sent' : s[0].toUpperCase() + s.slice(1),
      count: counts[s],
    })),
  )

  const visible = (rows ?? []).filter((q) => {
    if (tab !== 'all' && q.status !== tab) return false
    const term = search.trim().toLowerCase()
    if (!term) return true
    return `${q.id} ${q.customer_detail?.username} ${q.plan_detail?.name ?? ''}`.toLowerCase().includes(term)
  })

  const run = async (quotation, fn, success) => {
    setBusyId(quotation.id)
    try {
      await fn(quotation.id)
      toast.success(success)
      refresh()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  const accept = async (quotation) => {
    const selfRequested = quotation.created_by === quotation.customer
    const ok = await confirm({
      title: 'Accept this quotation?',
      message: selfRequested
        ? 'Your subscription starts straight away and your first invoice is issued.'
        : 'Our team will turn it into your subscription once you accept.',
      confirmLabel: 'Accept quotation',
    })
    if (ok) run(quotation, acceptQuotation, selfRequested ? 'Accepted. Your subscription is being set up.' : 'Quotation accepted.')
  }

  const reject = async (quotation) => {
    const ok = await confirm({ title: 'Reject this quotation?', message: 'The quotation will be closed and no subscription is created.', confirmLabel: 'Reject', tone: 'danger' })
    if (ok) run(quotation, rejectQuotation, 'Quotation rejected.')
  }

  const remove = async (quotation) => {
    const ok = await confirm({ title: `Delete quotation #${quotation.id}?`, message: 'Only drafts can be deleted, and this cannot be undone.', confirmLabel: 'Delete', tone: 'danger' })
    if (ok) run(quotation, deleteQuotation, 'Draft deleted.')
  }

  const columns = isCustomer ? 6 : 7

  return (
    <div>
      <PageHeader
        eyebrow={isCustomer ? 'My account' : 'Sales'}
        title={isCustomer ? 'My quotations' : 'Quotations'}
        subtitle={isCustomer ? 'Offers prepared for you. Accept one and your subscription follows.' : 'Draft, send and track offers until they become subscriptions.'}
        actions={
          !isCustomer && (
            <>
              <Link className="btn-secondary" to="/quotation-templates">
                Templates
              </Link>
              <Link className="btn-primary" to="/quotations/new">
                <Plus size={16} /> New quotation
              </Link>
            </>
          )
        }
      />

      <div className="toolbar">
        <FilterTabs tabs={tabs} value={tab} onChange={setTab} />
        <SearchInput value={search} onChange={setSearch} placeholder={isCustomer ? 'Search number or plan' : 'Search number, customer or plan'} />
      </div>

      {error && <p className="form-error">{error}</p>}

      {!rows && !error ? (
        <TableSkeleton rows={6} cols={columns} />
      ) : (
        rows && (
          <div className="table-card">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Quotation</th>
                  {!isCustomer && <th>Customer</th>}
                  <th>Plan</th>
                  <th className="num">Total</th>
                  <th>Valid until</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {visible.map((q) => {
                  const left = daysFromToday(q.valid_until)
                  const open = ['draft', 'sent'].includes(q.status)
                  return (
                    <tr key={q.id}>
                      <td className="doc">QUO-{String(q.id).padStart(4, '0')}</td>
                      {!isCustomer && <td className="strong">{q.customer_detail?.username}</td>}
                      <td>{q.plan_detail?.name ?? '—'}</td>
                      <td className="num strong">{money(q.total, 2)}</td>
                      <td>
                        <div className="cell-stack">
                          <span>{formatDate(q.valid_until)}</span>
                          {open && left !== null && (
                            <small className={`expiry-note ${left < 0 ? 'late' : ''}`}>
                              {left < 0 ? 'Past validity' : left === 0 ? 'Last day' : `${left} days left`}
                            </small>
                          )}
                        </div>
                      </td>
                      <td>
                        <StatusBadge status={q.status} />
                      </td>
                      <td className="table-actions">
                        {!isCustomer && q.status === 'draft' && <Link to={`/quotations/${q.id}/edit`}>Edit</Link>}
                        {!isCustomer && q.status === 'draft' && (
                          <button type="button" disabled={busyId === q.id} onClick={() => run(q, sendQuotation, 'Quotation sent to the customer.')}>
                            Send
                          </button>
                        )}
                        {!isCustomer && q.status === 'draft' && (
                          <button type="button" className="danger" disabled={busyId === q.id} onClick={() => remove(q)}>
                            Delete
                          </button>
                        )}
                        {q.status === 'sent' && (
                          <>
                            <button type="button" disabled={busyId === q.id} onClick={() => accept(q)}>
                              Accept
                            </button>
                            <button type="button" className="danger" disabled={busyId === q.id} onClick={() => reject(q)}>
                              Reject
                            </button>
                          </>
                        )}
                        {!isCustomer && q.status === 'accepted' && !q.subscription && (
                          <button
                            type="button"
                            disabled={busyId === q.id}
                            onClick={() => run(q, convertQuotation, 'Converted. The subscription is active and its first invoice is issued.')}
                          >
                            Convert to subscription
                          </button>
                        )}
                        {q.subscription && (
                          <Link className="link-quiet" to={`/subscriptions/${q.subscription}`}>
                            View subscription
                          </Link>
                        )}
                      </td>
                    </tr>
                  )
                })}
                {visible.length === 0 && (
                  <tr>
                    <td colSpan={columns} className="empty-cell">
                      <Empty icon={FileText} title="No quotations here">
                        {rows.length === 0 ? (isCustomer ? 'Request a plan from Browse plans to get one.' : 'Start from a template or build one from scratch.') : 'Try a different status or search.'}
                      </Empty>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  )
}
