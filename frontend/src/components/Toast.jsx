import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { CircleAlert, CircleCheck } from 'lucide-react'
import { Modal } from './ui'

const FeedbackContext = createContext(null)

/** Toasts and a promise-based confirm dialog, available anywhere through useToast() and useConfirm(). */
export function FeedbackProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const [dialog, setDialog] = useState(null)
  const nextId = useRef(1)

  const push = useCallback((kind, message) => {
    const id = nextId.current++
    setToasts((prev) => [...prev, { id, kind, message }])
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4200)
  }, [])

  const toast = useMemo(() => ({ success: (m) => push('success', m), error: (m) => push('error', m) }), [push])

  const confirm = useCallback(
    (options) =>
      new Promise((resolve) => {
        setDialog({ ...options, resolve })
      }),
    [],
  )

  const close = (answer) => {
    dialog?.resolve(answer)
    setDialog(null)
  }

  return (
    <FeedbackContext.Provider value={{ toast, confirm }}>
      {children}
      <div className="toast-stack" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`}>
            {t.kind === 'error' ? <CircleAlert size={18} /> : <CircleCheck size={18} />}
            <span>{t.message}</span>
          </div>
        ))}
      </div>
      <Modal
        open={Boolean(dialog)}
        title={dialog?.title ?? 'Are you sure?'}
        onClose={() => close(false)}
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => close(false)}>
              Cancel
            </button>
            <button type="button" className={dialog?.tone === 'danger' ? 'btn-danger' : 'btn-primary'} onClick={() => close(true)}>
              {dialog?.confirmLabel ?? 'Confirm'}
            </button>
          </>
        }
      >
        <p>{dialog?.message}</p>
      </Modal>
    </FeedbackContext.Provider>
  )
}

export function useToast() {
  return useContext(FeedbackContext).toast
}

export function useConfirm() {
  return useContext(FeedbackContext).confirm
}
