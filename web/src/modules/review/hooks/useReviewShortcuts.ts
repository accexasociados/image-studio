import { useEffect, useRef } from 'react'

type Handlers = {
  onApprove: () => void
  onReprocess: () => void
  onPrevious: () => void
  onNext: () => void
  onClose: () => void
}

const TYPING = new Set(['INPUT', 'SELECT', 'TEXTAREA'])

/** A aprobar, R reprocesar, ←/→ navegar y Esc cerrar; no actúa mientras se escribe en un campo. */
export function useReviewShortcuts(handlers: Handlers, enabled: boolean) {
  const latest = useRef(handlers)
  useEffect(() => {
    latest.current = handlers
  })

  useEffect(() => {
    if (!enabled) return
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const typing = target && (TYPING.has(target.tagName) || target.isContentEditable)
      if (event.ctrlKey || event.metaKey || event.altKey) return
      const actions: Record<string, (() => void) | undefined> = {
        Escape: latest.current.onClose,
        ArrowLeft: typing ? undefined : latest.current.onPrevious,
        ArrowRight: typing ? undefined : latest.current.onNext,
        a: typing ? undefined : latest.current.onApprove,
        r: typing ? undefined : latest.current.onReprocess,
      }
      const action = actions[event.key.length === 1 ? event.key.toLowerCase() : event.key]
      if (!action) return
      event.preventDefault()
      action()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [enabled])
}
