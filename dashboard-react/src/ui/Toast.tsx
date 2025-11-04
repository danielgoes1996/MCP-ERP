import { ReactNode, useEffect, useMemo, useState } from 'react'

type ToastIntent = 'info' | 'success' | 'warning' | 'danger'

type ToastItem = {
  id: string
  title?: ReactNode
  message?: ReactNode
  intent: ToastIntent
}

type ToastContextValue = {
  toasts: ToastItem[]
  show: (toast: Omit<ToastItem, 'id'>) => void
  dismiss: (id: string) => void
}

const listeners = new Set<(value: ToastContextValue) => void>()
let queue: ToastItem[] = []

function emit() {
  const value = {
    toasts: queue,
    show,
    dismiss,
  }
  listeners.forEach((listener) => listener(value))
}

function show(toast: Omit<ToastItem, 'id'>) {
  const item: ToastItem = { id: crypto.randomUUID(), ...toast }
  queue = [...queue, item]
  emit()
  return item.id
}

function dismiss(id: string) {
  queue = queue.filter((item) => item.id !== id)
  emit()
}

export function subscribe(listener: (value: ToastContextValue) => void) {
  listeners.add(listener)
  emit()
  return () => {
    listeners.delete(listener)
  }
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ToastContextValue>(() => ({
    toasts: [],
    show,
    dismiss,
  }))

  useEffect(() => {
    const unsubscribe = subscribe(setState)
    return () => unsubscribe()
  }, [])

  return (
    <>
      {children}
      <div className="toast-container">
        {state.toasts.map((toast) => (
          <div key={toast.id} className={`toast toast--${toast.intent}`} role={toast.intent === 'danger' ? 'alert' : 'status'}>
            <div className="toast__body">
              {toast.title ? <strong className="toast__title">{toast.title}</strong> : null}
              {toast.message ? <p className="toast__message">{toast.message}</p> : null}
            </div>
            <button className="toast__close" type="button" onClick={() => state.dismiss(toast.id)} aria-label="Cerrar notificación">
              ×
            </button>
          </div>
        ))}
      </div>
    </>
  )
}

export function useToast() {
  return useMemo(() => ({ show, dismiss }), [])
}
