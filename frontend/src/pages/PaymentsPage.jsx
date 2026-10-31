import { useState } from 'react'
import { Link } from 'react-router-dom'
import { HandCoins, Wallet } from 'lucide-react'
import { PAYMENT_METHODS } from '../api/billing'
import { Empty, PageHeader, Pagination, SearchInput, TableSkeleton, formatDate, money } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useDebounced, usePaged } from '../hooks/usePaged'
import './Billing.css'

const METHOD_LABEL = Object.fromEntries(PAYMENT_METHODS.map((m) => [m.value, m.label]))

export default function PaymentsPage() {
  const { user } = useAuth()
  const isCustomer = user.role === 'customer'
  const [search, setSearch] = useState('')
  const [method, setMethod] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const q = useDebounced(search)

  const { rows, count, page, setPage, loading, error, pageSize } = usePaged('/payments/', { q, method, from, to })
  const columns = isCustomer ? 5 : 6

  return (
    <div>
      <PageHeader
        eyebrow="Billing"
        title={isCustomer ? 'Payment history' : 'Payments'}
        subtitle={isCustomer ? 'Every payment received on your account.' : 'Every payment, matched to the invoice it settled.'}
        actions={
          !isCustomer && (
            <Link className="btn-primary" to="/payments/new">
              <HandCoins size={16} /> Record payment
            </Link>
          )
        }
      />

      <div className="toolbar">
        <div className="toolbar-group">
          <select className="select-compact" value={method} onChange={(e) => setMethod(e.target.value)} aria-label="Payment method">
            <option value="">All methods</option>
            {PAYMENT_METHODS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
          <label className="date-range">
            <span>Paid</span>
            <input type="date" value={from} max={to || undefined} onChange={(e) => setFrom(e.target.value)} aria-label="Paid from" />
            <span>to</span>
            <input type="date" value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} aria-label="Paid to" />
          </label>
        </div>
        <SearchInput value={search} onChange={setSearch} placeholder={isCustomer ? 'Search invoice number' : 'Search invoice or customer'} />
      </div>

      {error && <p className="form-error">{error}</p>}

      {loading && rows.length === 0 ? (
        <TableSkeleton rows={8} cols={columns} />
      ) : (
        <div className={`table-card ${loading ? 'is-refreshing' : ''}`}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Invoice</th>
                {!isCustomer && <th>Customer</th>}
                <th>Method</th>
                <th>Note</th>
                <th className="num">Amount</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((payment) => (
                <tr key={payment.id}>
                  <td>{formatDate(payment.paid_on)}</td>
                  <td>
                    <Link className="doc" to={`/invoices/${payment.invoice}`}>
                      {payment.invoice_number}
                    </Link>
                  </td>
                  {!isCustomer && <td className="strong">{payment.customer_name}</td>}
                  <td>{METHOD_LABEL[payment.method] ?? payment.method}</td>
                  <td>{payment.note || '—'}</td>
                  <td className="num strong">{money(payment.amount, 2)}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={columns} className="empty-cell">
                    <Empty icon={Wallet} title="No payments found">
                      {q || method || from || to ? 'Try a different filter.' : 'Payments show up here once they are recorded against an invoice.'}
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
