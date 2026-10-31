import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Check, ChevronLeft, ChevronRight, Inbox, Search, X } from 'lucide-react'
import './ui.css'

/* ---------------------------------------------------------------- formatters */

export function money(value, digits = 0) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(Number(value ?? 0))
}

export function compactMoney(value) {
  const n = Number(value ?? 0)
  if (Math.abs(n) >= 10000000) return `₹${(n / 10000000).toFixed(2)} Cr`
  if (Math.abs(n) >= 100000) return `₹${(n / 100000).toFixed(2)} L`
  return money(n)
}

export function formatDate(value) {
  if (!value) return '—'
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T00:00:00`) : new Date(value)
  return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function formatDateTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function daysFromToday(value) {
  if (!value) return null
  const target = new Date(`${value}T00:00:00`)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.round((target - today) / 86400000)
}

export function relativeDays(value) {
  const diff = daysFromToday(value)
  if (diff === null) return '—'
  if (diff === 0) return 'today'
  if (diff === 1) return 'tomorrow'
  if (diff === -1) return 'yesterday'
  return diff > 0 ? `in ${diff} days` : `${-diff} days ago`
}

export const FREQUENCY_LABEL = { daily: 'day', weekly: 'week', monthly: 'month', quarterly: 'quarter', yearly: 'year' }

/* ---------------------------------------------------------------- status */

const TONES = {
  active: 'success',
  paid: 'success',
  accepted: 'success',
  confirmed: 'info',
  sent: 'info',
  quotation: 'info',
  pending: 'warning',
  paused: 'warning',
  scheduled: 'warning',
  draft: 'neutral',
  expired: 'neutral',
  closed: 'neutral',
  disabled: 'neutral',
  rejected: 'danger',
  cancelled: 'danger',
  overdue: 'danger',
  exhausted: 'danger',
  admin: 'amber',
  staff: 'info',
  customer: 'neutral',
}

export function StatusBadge({ status, label }) {
  return (
    <span className={`badge badge-${TONES[status] ?? 'neutral'}`}>
      <i />
      {label ?? status}
    </span>
  )
}

/* ---------------------------------------------------------------- layout blocks */

export function PageHeader({ eyebrow, title, subtitle, actions }) {
  return (
    <div className="page-header">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}

export function Panel({ title, subtitle, action, children, className = '', flush = false }) {
  return (
    <section className={`panel ${className}`}>
      {(title || action) && (
        <header className="panel-header">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <p>{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={flush ? 'panel-body flush' : 'panel-body'}>{children}</div>
    </section>
  )
}

export function Sparkline({ values, tone = 'pine', width = 96, height = 30 }) {
  const points = values.map(Number)
  if (points.length < 2) return null
  const min = Math.min(...points)
  const max = Math.max(...points)
  const span = max - min || 1
  const step = width / (points.length - 1)
  const coords = points.map((v, i) => [i * step, height - 3 - ((v - min) / span) * (height - 6)])
  const line = coords.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ')
  const area = `${line} L${width} ${height} L0 ${height} Z`
  return (
    <svg className={`spark spark-${tone}`} width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <path d={area} className="spark-area" />
      <path d={line} className="spark-line" />
      <circle cx={coords.at(-1)[0]} cy={coords.at(-1)[1]} r="2.4" className="spark-dot" />
    </svg>
  )
}

export function Kpi({ label, value, hint, delta, spark, tone = 'pine', icon: Icon }) {
  return (
    <div className={`kpi kpi-${tone}`}>
      <div className="kpi-top">
        <span className="kpi-label">{label}</span>
        {Icon && <Icon size={16} />}
      </div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-foot">
        <span className="kpi-hint">
          {delta !== undefined && delta !== null && (
            <b className={delta >= 0 ? 'up' : 'down'}>
              {delta >= 0 ? '+' : ''}
              {delta}
            </b>
          )}
          {hint}
        </span>
        {spark && <Sparkline values={spark} tone={tone} />}
      </div>
    </div>
  )
}

export const StatCard = ({ icon, label, value, hint, tone }) => (
  <Kpi icon={icon} label={label} value={value} hint={hint} tone={tone === 'danger' ? 'clay' : tone === 'warning' ? 'amber' : 'pine'} />
)

export function QuickActions({ actions }) {
  return (
    <div className="quick-actions">
      {actions.map(({ to, label, icon: Icon }) => (
        <Link key={label} to={to} className="quick-action">
          <Icon size={16} />
          <span>{label}</span>
        </Link>
      ))}
    </div>
  )
}

export function Empty({ title, children, icon: Icon = Inbox }) {
  return (
    <div className="empty">
      <Icon size={22} />
      {title && <strong>{title}</strong>}
      {children && <span>{children}</span>}
    </div>
  )
}

export function ListRow({ title, meta, aside, asideMeta, to }) {
  const body = (
    <>
      <div className="list-main">
        <span className="list-title">{title}</span>
        {meta && <span className="list-meta">{meta}</span>}
      </div>
      {(aside || asideMeta) && (
        <div className="list-aside">
          {aside}
          {asideMeta && <span className="list-meta">{asideMeta}</span>}
        </div>
      )}
    </>
  )
  return to ? (
    <Link className="list-row linked" to={to}>
      {body}
    </Link>
  ) : (
    <div className="list-row">{body}</div>
  )
}

const AVATAR_TINTS = ['#12493b', '#8a5a14', '#6b3b2e', '#2c5d73', '#5b4a7a', '#43603a']

export function Avatar({ name, size = 34 }) {
  const label = (name ?? '?').slice(0, 2).toUpperCase()
  const tint = AVATAR_TINTS[[...label].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % AVATAR_TINTS.length]
  return (
    <span className="avatar" style={{ width: size, height: size, background: tint, fontSize: size * 0.34 }}>
      {label}
    </span>
  )
}

/* ---------------------------------------------------------------- loading + paging */

export function Skeleton({ height = 14, width = '100%', radius = 6 }) {
  return <span className="skeleton" style={{ height, width, borderRadius: radius }} />
}

export function TableSkeleton({ rows = 6, cols = 5 }) {
  return (
    <div className="table-card">
      <table className="data-table">
        <tbody>
          {Array.from({ length: rows }, (_, r) => (
            <tr key={r}>
              {Array.from({ length: cols }, (_, c) => (
                <td key={c}>
                  <Skeleton width={c === 0 ? '70%' : '55%'} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function PageSkeleton() {
  return (
    <div className="page-skeleton">
      <Skeleton height={34} width={280} radius={8} />
      <div className="kpi-grid">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} height={104} radius={12} />
        ))}
      </div>
      <Skeleton height={280} radius={12} />
    </div>
  )
}

export function Pagination({ page, pageSize = 20, count, onPage }) {
  const pages = Math.max(1, Math.ceil(count / pageSize))
  if (count <= pageSize) {
    return count > 0 ? <div className="pagination"><span>{count} {count === 1 ? 'record' : 'records'}</span></div> : null
  }
  const from = (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, count)
  return (
    <div className="pagination">
      <span>
        {from}-{to} of {count}
      </span>
      <div className="pagination-buttons">
        <button type="button" className="btn-secondary btn-small" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          <ChevronLeft size={14} /> Prev
        </button>
        <span className="pagination-page">
          {page} / {pages}
        </span>
        <button type="button" className="btn-secondary btn-small" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next <ChevronRight size={14} />
        </button>
      </div>
    </div>
  )
}

export function FilterTabs({ tabs, value, onChange }) {
  return (
    <div className="filter-tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.value}
          type="button"
          role="tab"
          aria-selected={value === tab.value}
          className={value === tab.value ? 'active' : ''}
          onClick={() => onChange(tab.value)}
        >
          {tab.label}
          {tab.count !== undefined && <em>{tab.count}</em>}
        </button>
      ))}
    </div>
  )
}

export function SearchInput({ value, onChange, placeholder = 'Search' }) {
  return (
    <label className="search-input">
      <Search size={15} />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
      {value && (
        <button type="button" onClick={() => onChange('')} aria-label="Clear search">
          <X size={14} />
        </button>
      )}
    </label>
  )
}

/* ---------------------------------------------------------------- forms */

export function Field({ label, error, hint, children, className = '' }) {
  return (
    <label className={`field ${className}`}>
      <span className="field-label">{label}</span>
      {children}
      {hint && !error && <span className="field-hint">{hint}</span>}
      {error && <span className="field-error">{[].concat(error).join(' ')}</span>}
    </label>
  )
}

export function Modal({ open, title, onClose, children, footer, wide = false }) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className={`modal ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" aria-label={title} onMouseDown={(e) => e.stopPropagation()}>
        <header>
          <h2>{title}</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer>{footer}</footer>}
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- workflow + history */

export function Stepper({ steps, current }) {
  const index = steps.findIndex((s) => s.value === current)
  return (
    <ol className="stepper">
      {steps.map((step, i) => (
        <li key={step.value} className={i < index ? 'done' : i === index ? 'current' : ''}>
          <span className="stepper-dot">{i < index ? <Check size={12} /> : i + 1}</span>
          <span className="stepper-label">{step.label}</span>
        </li>
      ))}
    </ol>
  )
}

export function Timeline({ items }) {
  return (
    <ul className="timeline">
      {items.map((item, i) => (
        <li key={i}>
          <span className="timeline-dot" />
          <div>
            <p>{item.title}</p>
            <span>{item.meta}</span>
          </div>
        </li>
      ))}
    </ul>
  )
}

export function Avatars({ names }) {
  return (
    <div className="avatar-stack">
      {names.map((name) => (
        <Avatar key={name} name={name} size={26} />
      ))}
    </div>
  )
}
