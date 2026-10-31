import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CornerDownLeft, FileText, Receipt, Repeat, Search, Users } from 'lucide-react'
import api from '../api/client'
import { flatNav } from '../nav'
import { useDebounced } from '../hooks/usePaged'
import './CommandPalette.css'

const RESULT_ICON = { subscription: Repeat, invoice: Receipt, customer: Users, quotation: FileText }

export default function CommandPalette({ open, onClose, role }) {
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const [query, setQuery] = useState('')
  const [remote, setRemote] = useState([])
  const [cursor, setCursor] = useState(0)
  const term = useDebounced(query.trim(), 200)

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 20)
    else {
      setQuery('')
      setRemote([])
    }
  }, [open])

  useEffect(() => {
    if (!open || term.length < 2) {
      setRemote([])
      return
    }
    api
      .get('/search/', { params: { q: term } })
      .then(({ data }) => setRemote(data.results))
      .catch(() => setRemote([]))
  }, [term, open])

  const pages = useMemo(() => {
    const q = query.trim().toLowerCase()
    return flatNav(role)
      .filter((item) => !q || item.label.toLowerCase().includes(q))
      .map((item) => ({ key: item.to, title: item.label, subtitle: 'Go to page', icon: item.icon, url: item.to }))
  }, [query, role])

  const results = useMemo(
    () => [
      ...remote.map((r) => ({
        key: `${r.type}-${r.id}`,
        title: r.title,
        subtitle: `${r.type.charAt(0).toUpperCase()}${r.type.slice(1)}  ·  ${r.subtitle}`,
        icon: RESULT_ICON[r.type] ?? Search,
        url: r.url,
        mono: true,
      })),
      ...pages,
    ],
    [remote, pages],
  )

  useEffect(() => setCursor(0), [query, remote])

  if (!open) return null

  const go = (item) => {
    onClose()
    navigate(item.url)
  }

  const onKeyDown = (e) => {
    if (e.key === 'Escape') onClose()
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setCursor((c) => Math.min(c + 1, results.length - 1))
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setCursor((c) => Math.max(c - 1, 0))
    }
    if (e.key === 'Enter' && results[cursor]) go(results[cursor])
  }

  return (
    <div className="palette-backdrop" onMouseDown={onClose}>
      <div className="palette" role="dialog" aria-label="Search" onMouseDown={(e) => e.stopPropagation()}>
        <div className="palette-input">
          <Search size={18} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search customers, subscriptions, invoices or jump to a page"
          />
          <kbd>Esc</kbd>
        </div>
        <ul className="palette-list">
          {results.length === 0 && <li className="palette-empty">Nothing matches &quot;{query}&quot;</li>}
          {results.map((item, index) => {
            const Icon = item.icon
            return (
              <li key={item.key}>
                <button
                  type="button"
                  className={index === cursor ? 'active' : ''}
                  onMouseEnter={() => setCursor(index)}
                  onClick={() => go(item)}
                >
                  <Icon size={16} />
                  <span className={item.mono ? 'mono' : ''}>{item.title}</span>
                  <small>{item.subtitle}</small>
                  {index === cursor && <CornerDownLeft size={14} />}
                </button>
              </li>
            )
          })}
        </ul>
      </div>
    </div>
  )
}
