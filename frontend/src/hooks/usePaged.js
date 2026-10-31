import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../api/client'

export function useDebounced(value, delay = 300) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}

/**
 * Loads a paginated list endpoint (DRF page-number pagination).
 * Changing `params` resets to page 1. Returns { rows, count, page, setPage, loading, error, reload, pageSize }.
 */
export function usePaged(path, params = {}, pageSize = 20) {
  const [rows, setRows] = useState([])
  const [count, setCount] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tick, setTick] = useState(0)
  const key = JSON.stringify(params)
  const latest = useRef(0)

  useEffect(() => {
    setPage(1)
  }, [key])

  useEffect(() => {
    const request = ++latest.current
    const query = { ...JSON.parse(key), page, page_size: pageSize }
    Object.keys(query).forEach((k) => (query[k] === '' || query[k] == null) && delete query[k])
    setLoading(true)
    api
      .get(path, { params: query })
      .then(({ data }) => {
        if (request !== latest.current) return
        setRows(data.results)
        setCount(data.count)
        setError('')
      })
      .catch(() => request === latest.current && setError('Could not load this list. Please try again.'))
      .finally(() => request === latest.current && setLoading(false))
  }, [path, key, page, pageSize, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { rows, count, page, setPage, loading, error, reload, pageSize }
}
