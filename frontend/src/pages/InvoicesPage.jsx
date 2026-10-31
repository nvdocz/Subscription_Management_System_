import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { CheckCheck, HandCoins, Receipt } from 'lucide-react'
import { confirmDrafts } from '../api/billing'
import { useConfirm, useToast } from '../components/Toast'
import {
  Empty,
  FilterTabs,
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
import './Billing.css'

const STAFF_TABS = [
  { value: 'all', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'overdue', label: 'Overdue' },
  { value: 'paid', label: 'Paid' },
  { value: 'cancelled', label: 'Cancelled' },
]

const CUSTOMER_TABS = [
  { value: 'all', label: 'All' },
  { value: 'confirmed', label: 'Open' },
  { value: 'overdue', label: 'Overdue' },
  { value: 'paid', label: 'Paid' },
]

function tabParams(tab) {
  if (tab === 'all') return {}
  if (tab === 'overdue') return { overdue: '1' }
  return { status: tab }
}

export default function InvoicesPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()
  const isCustomer = user.role === 'customer'

  const [params, setParams] = useSearchParams()
  const tabs = isCustomer ? CUSTOMER_TABS : STAFF_TABS
  const requested = params.get('overdue') === '1' ? 'overdue' : params.get('status')
  const tab = tabs.some((t) => t.value === requested) ? requested : 'all'
  const setTab = (value) =>
    setParams(value === 'all' ? {} : value === 'overdue' ? { overdue: '1' } : { status: value }, { replace: true })
  const [search, setSearch] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const q = useDebounced(search)

  const { rows, count, page, setPage, loading, error, reload, pageSize } = usePaged('/invoices/', {
    ...tabParams(tab),
    q,
    from,
    to,
  })

  const handleConfirmDrafts = async () => {
    const ok = await confirm({
      title: 'Confirm all draft invoices?',
      message: 'Every draft invoice becomes confirmed and can then be paid. This cannot be undone in bulk.',
      confirmLabel: 'Confirm drafts',
    })
    if (!ok) return
    try {
      const { confirmed } = await confirmDrafts()
      toast.success(confirmed ? `${confirmed} draft invoice${confirmed === 1 ? '' : 's'} confirmed.` : 'There were no drafts to confirm.')
      reload()
    } catch {
      toast.error('Could not confirm the drafts.')
    }
  }

  const columns = isCustomer ? 8 : 9

  return (
    <div>
      <PageHeader
        eyebrow="Billing"
        title="Invoices"
        subtitle={isCustomer ? 'Everything we have billed you, and what is still due.' : 'Created from subscriptions. Confirm, send, collect.'}
        actions={
          !isCustomer && (
            <>
              <button type="button" className="btn-secondary" onClick={handleConfirmDrafts}>
                <CheckCheck size={16} /> Confirm all drafts
              </button>
              <Link className="btn-primary" to="/payments/new">
                <HandCoins size={16} /> Record payment
              </Link>
            </>
          )
        }
      />

      <div className="toolbar">
        <FilterTabs tabs={tabs} value={tab} onChange={setTab} />
        <div className="toolbar-group">
          <label className="date-range">
            <span>Issued</span>
            <input type="date" value={from} max={to || undefined} onChange={(e) => setFrom(e.target.value)} aria-label="Issued from" />
            <span>to</span>
            <input type="date" value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} aria-label="Issued to" />
          </label>
          <SearchInput value={search} onChange={setSearch} placeholder={isCustomer ? 'Search invoice number' : 'Search number or customer'} />
        </div>
      </div>

      {error && <p className="form-error">{error}</p>}

      {loading && rows.length === 0 ? (
        <TableSkeleton rows={8} cols={columns} />
      ) : (
        <div className={`table-card ${loading ? 'is-refreshing' : ''}`}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Invoice</th>
                {!isCustomer && <th>Customer</th>}
                <th>Subscription</th>
                <th>Billing period</th>
                <th>Due</th>
                <th className="num">Amount</th>
                <th className="num">Balance</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((invoice) => (
                <tr key={invoice.id} className="row-link" onClick={() => navigate(`/invoices/${invoice.id}`)}>
                  <td className="doc">{invoice.number}</td>
                  {!isCustomer && <td className="strong">{invoice.customer_detail.username}</td>}
                  <td className="doc">{invoice.subscription_number ?? '—'}</td>
                  <td>
                    {invoice.period_start ? `${formatDate(invoice.period_start)} to ${formatDate(invoice.period_end)}` : '—'}
                  </td>
                  <td>{formatDate(invoice.due_date)}</td>
                  <td className="num strong">{money(invoice.amount, 2)}</td>
                  <td className="num">{invoice.status === 'confirmed' ? money(invoice.balance, 2) : '—'}</td>
                  <td>
                    <StatusBadge status={invoice.is_overdue ? 'overdue' : invoice.status} />
                  </td>
                  <td className="table-actions" onClick={(e) => e.stopPropagation()}>
                    {isCustomer && invoice.status === 'confirmed' && (
                      <Link className="pay-link" to={`/invoices/${invoice.id}`}>
                        Pay now
                      </Link>
                    )}
                    {!isCustomer && invoice.status === 'confirmed' && (
                      <Link to={`/payments/new?invoice=${invoice.id}`}>Record payment</Link>
                    )}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={columns} className="empty-cell">
                    <Empty icon={Receipt} title="No invoices match">
                      {tab === 'all' && !q && !from && !to
                        ? 'Invoices appear here as subscriptions are billed.'
                        : 'Try a different status, date range or search.'}
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
