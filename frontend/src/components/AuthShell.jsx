import { Check } from 'lucide-react'
import { BrandMark, Wordmark } from './Brand'
import { Sparkline } from './ui'
import './AuthShell.css'

export const PASSWORD_RULES = [
  { label: 'More than 8 characters', test: (p) => p.length > 8 },
  { label: 'An uppercase letter', test: (p) => /[A-Z]/.test(p) },
  { label: 'A lowercase letter', test: (p) => /[a-z]/.test(p) },
  { label: 'A special character', test: (p) => /[^A-Za-z0-9]/.test(p) },
]

export function PasswordRules({ password }) {
  return (
    <ul className="password-rules">
      {PASSWORD_RULES.map((rule) => {
        const ok = rule.test(password)
        return (
          <li key={rule.label} className={ok ? 'ok' : ''}>
            <span>{ok && <Check size={11} />}</span>
            {rule.label}
          </li>
        )
      })}
    </ul>
  )
}

export function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="auth-shell">
      <section className="auth-story">
        <div className="auth-brand">
          <BrandMark size={38} />
          <Wordmark light />
        </div>

        <div className="auth-copy-block">
          <h2>
            Recurring revenue,
            <br />
            run properly.
          </h2>
          <p>Plans, subscriptions, invoices and payments in one ledger. Nothing billed twice, nothing missed.</p>
        </div>

        <div className="auth-preview" aria-hidden="true">
          <div className="auth-preview-head">
            <span>Monthly recurring revenue</span>
            <em>+12.4%</em>
          </div>
          <strong>₹ 2,84,500</strong>
          <Sparkline values={[12, 14, 13, 18, 21, 20, 26, 29, 34]} tone="amber" width={300} height={54} />
          <div className="auth-preview-rows">
            <div>
              <i className="dot ok" /> INV-00231 <b>Paid</b>
            </div>
            <div>
              <i className="dot warn" /> INV-00232 <b>Due in 4 days</b>
            </div>
            <div>
              <i className="dot ok" /> SUB-00118 <b>Renewed</b>
            </div>
          </div>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <header>
            <h1>{title}</h1>
            {subtitle && <p>{subtitle}</p>}
          </header>
          {children}
          {footer && <footer>{footer}</footer>}
        </div>
      </section>
    </div>
  )
}
