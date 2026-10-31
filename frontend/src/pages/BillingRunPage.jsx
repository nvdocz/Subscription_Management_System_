import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Play, ShieldCheck } from 'lucide-react'
import { getBillingPreview, runBilling } from '../api/billing'
import { useConfirm, useToast } from '../components/Toast'
import { Empty, PageHeader, Panel, Skeleton, formatDate, money } from '../components/ui'
import './Billing.css'

export default function BillingRunPage() {
  const toast = useToast()
  const confirm = useConfirm()
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  const [autoConfirm, setAutoConfirm] = useState(false)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)

  const load = useCallback(() => {
    return getBillingPreview()
      .then((data) => {
        setPreview(data)
        setError('')
      })
      .catch(() => setError('Could not load the billing preview.'))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleRun = async () => {
    const ok = await confirm({
      title: 'Run billing now?',
      message: `${preview.due_count} subscription${preview.due_count === 1 ? ' is' : 's are'} due. ${
        autoConfirm ? 'Invoices will be confirmed as they are created.' : 'Invoices will be created as drafts for you to review.'
      }`,
      confirmLabel: 'Run billing',
    })
    if (!ok) return
    setRunning(true)
    try {
      const data = await runBilling(autoConfirm)
      setResult(data)
      toast.success(
        data.invoices_created
          ? `${data.invoices_created} invoice${data.invoices_created === 1 ? '' : 's'} created.`
          : 'Nothing was due, so nothing was billed.',
      )
      await load()
    } catch {
      toast.error('The billing run failed. Nothing was lost; you can run it again.')
    } finally {
      setRunning(false)
    }
  }

  const nothingDue = preview && preview.due_count === 0

  return (
    <div>
      <PageHeader
        eyebrow="Billing"
        title="Billing run"
        subtitle="Create this period's invoices from active subscriptions, with taxes and discounts already applied."
      />

      {error && <p className="form-error">{error}</p>}

      <div className="run-layout">
        <Panel
          title="Due for billing"
          subtitle={preview ? `As of ${formatDate(preview.as_of)}` : undefined}
          flush
        >
          {!preview ? (
            <div style={{ padding: 20 }}>
              <Skeleton height={180} radius={10} />
            </div>
          ) : (
            <>
              <div className="run-summary" style={{ padding: '10px 20px 16px' }}>
                <div className="run-figure">
                  <span>Subscriptions due</span>
                  <strong>{preview.due_count}</strong>
                </div>
                <div className="run-figure">
                  <span>Estimated before tax</span>
                  <strong>{money(preview.estimated_total, 2)}</strong>
                </div>
              </div>

              {nothingDue ? (
                <Empty icon={ShieldCheck} title="Everything is up to date">
                  No subscription has a billing date on or before today.
                </Empty>
              ) : (
                <div className="table-card" style={{ border: 'none', borderTop: '1px solid var(--line)', borderRadius: 0, boxShadow: 'none' }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Subscription</th>
                        <th>Customer</th>
                        <th>Plan</th>
                        <th>Billing date</th>
                        <th className="num">Estimate</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.rows.map((row) => (
                        <tr key={row.subscription}>
                          <td>
                            <Link className="doc" to={`/subscriptions/${row.subscription}`}>
                              {row.number}
                            </Link>
                          </td>
                          <td className="strong">{row.customer}</td>
                          <td>{row.plan}</td>
                          <td>{formatDate(row.billing_date)}</td>
                          <td className="num">{money(row.estimated_amount, 2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {preview.due_count > preview.rows.length && (
                    <p className="list-meta" style={{ padding: '10px 16px' }}>
                      Showing the first {preview.rows.length} of {preview.due_count}. The run bills all of them.
                    </p>
                  )}
                </div>
              )}
            </>
          )}
        </Panel>

        <Panel title="Run it">
          <div className="run-control">
            <p>
              Each subscription is billed once per period. Taxes follow the admin tax rules and eligible discounts are applied
              automatically.
            </p>
            <label className="check-row">
              <input type="checkbox" checked={autoConfirm} onChange={(e) => setAutoConfirm(e.target.checked)} />
              <span>
                Confirm invoices automatically
                <small>Leave off to review drafts first.</small>
              </span>
            </label>
            <button type="button" className="btn-primary" disabled={!preview || nothingDue || running} onClick={handleRun}>
              <Play size={15} /> {running ? 'Billing...' : 'Run billing now'}
            </button>
            <div className="run-note">
              <ShieldCheck size={16} />
              <span>Safe to run again. A period that already has an invoice is skipped, so nothing is billed twice.</span>
            </div>
          </div>
        </Panel>
      </div>

      {result && (
        <Panel title="Last run" subtitle={`Completed for ${formatDate(result.as_of)}`} className="run-result">
          <div className="run-result-grid">
            <div>
              <strong>{result.invoices_created}</strong>
              <span>Invoices created</span>
            </div>
            <div>
              <strong>{money(result.total_billed, 2)}</strong>
              <span>Total billed</span>
            </div>
            <div>
              <strong>{result.periods_skipped}</strong>
              <span>Already billed, skipped</span>
            </div>
            <div>
              <strong>{result.activated}</strong>
              <span>Subscriptions activated</span>
            </div>
            <div>
              <strong>{result.auto_closed}</strong>
              <span>Auto-closed at expiry</span>
            </div>
          </div>
          {result.invoices.length > 0 && (
            <div className="table-card" style={{ boxShadow: 'none' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Invoice</th>
                    <th>Customer</th>
                    <th className="num">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {result.invoices.map((invoice) => (
                    <tr key={invoice.id}>
                      <td>
                        <Link className="doc" to={`/invoices/${invoice.id}`}>
                          {invoice.number}
                        </Link>
                      </td>
                      <td className="strong">{invoice.customer}</td>
                      <td className="num">{money(invoice.amount, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}
    </div>
  )
}
