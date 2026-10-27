import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

/** Aviso del navegador al terminar cualquier lote; el permiso se pide con un clic (Chrome lo exige). */
export function useBrowserNotifications() {
  const { t } = useTranslation()
  const [permission, setPermission] = useState<NotificationPermission | 'unsupported'>(() =>
    typeof Notification === 'undefined' ? 'unsupported' : Notification.permission,
  )

  const requestPermission = useCallback(() => {
    if (typeof Notification === 'undefined') return
    void Notification.requestPermission().then(setPermission)
  }, [])

  useEffect(() => {
    if (permission !== 'granted') return
    const stream = new EventSource('/api/v1/events')
    const onFinished = (event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as { batch_id?: string; batch_name?: string }
        new Notification(payload.batch_name ?? t('app.title'), {
          body: t('batches.browserFinished'),
          tag: payload.batch_id ? `batch-${payload.batch_id}` : undefined,
        })
      } catch {
        // Un evento mal formado no debe detener el canal global.
      }
    }
    stream.addEventListener('batch.finished', onFinished)
    return () => {
      stream.removeEventListener('batch.finished', onFinished)
      stream.close()
    }
  }, [permission, t])

  return { permission, requestPermission }
}
