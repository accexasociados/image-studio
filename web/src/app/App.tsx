import { useTranslation } from 'react-i18next'
import { HealthStatus } from '@/modules/health/components/HealthStatus'
import { saveLanguage } from './i18n/i18n'
import type { Language } from './i18n/translations'

export function App() {
  const { t, i18n } = useTranslation()

  const changeLanguage = (language: Language) => {
    void i18n.changeLanguage(language)
    saveLanguage(language)
  }

  return (
    <div className="min-h-screen bg-neutral-50 text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
      <header className="border-b border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-4">
          <div>
            <h1 className="text-lg font-semibold">{t('app.title')}</h1>
            <p className="text-sm text-neutral-500">{t('app.subtitle')}</p>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <span className="text-neutral-500">{t('common.language')}</span>
            <select
              className="rounded-md border border-neutral-300 bg-transparent px-2 py-1 dark:border-neutral-700"
              value={i18n.language}
              onChange={(event) => changeLanguage(event.target.value as Language)}
            >
              <option value="es">{t('common.spanish')}</option>
              <option value="en">{t('common.english')}</option>
            </select>
          </label>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <HealthStatus />
      </main>
    </div>
  )
}
