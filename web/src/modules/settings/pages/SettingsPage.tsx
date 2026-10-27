import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { apiGet, apiPost, apiPut, type AppSettingsPublic, type ProcessOptions } from '@/shared/api/client'
import { ProcessOptionsFields } from '@/shared/components/ProcessOptionsFields'
import { FALLBACK_OPTIONS } from '@/shared/components/processOptions'

const SECTIONS = [
  'general',
  'processing_defaults',
  'export',
  'telegram',
  'notifications',
  'hot_folder',
  'importers',
  'quality',
  'pipeline',
] as const
type Section = (typeof SECTIONS)[number]
type Values = Record<string, unknown>

export function SettingsPage({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation()
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ['settings'],
    queryFn: () => apiGet<AppSettingsPublic>('/settings'),
  })
  const [section, setSection] = useState<Section>('general')
  const [values, setValues] = useState<Values>({})
  const [message, setMessage] = useState('')
  const [testingTelegram, setTestingTelegram] = useState(false)
  const current = data?.[section] as unknown as Values | undefined
  const draft = Object.keys(values).length > 0 ? values : (current ?? {})
  const update = (key: string, value: unknown) => setValues((old) => ({ ...old, [key]: value }))
  const save = async () => {
    const response = await apiPut<AppSettingsPublic>(`/settings/${section}`, draft)
    setMessage(t('settings.saved'))
    await refetch()
    setValues(response[section] as unknown as Values)
  }
  const testTelegram = async () => {
    setTestingTelegram(true)
    try {
      await apiPost('/settings/telegram/test', {})
      setMessage(t('settings.telegramOk'))
    } catch {
      setMessage(t('settings.telegramError'))
    }
    setTestingTelegram(false)
  }

  return (
    <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-950 dark:text-white">{t('settings.title')}</h1>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{t('settings.description')}</p>
        </div>
        <button type="button" onClick={onClose} className="text-sm font-semibold text-indigo-600">
          {t('settings.back')}
        </button>
      </div>
      {isPending && <p>{t('common.loading')}</p>}
      {isError && <p role="alert">{t('settings.error')}</p>}
      {data && (
        <div className="grid gap-6 lg:grid-cols-[15rem_1fr]">
          <nav className="flex gap-2 overflow-auto lg:flex-col">
            {SECTIONS.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => {
                  setSection(item)
                  setValues(data[item] as unknown as Values)
                }}
                className={`whitespace-nowrap rounded-lg px-3 py-2 text-left text-sm font-semibold ${section === item ? 'bg-indigo-600 text-white' : 'bg-white text-slate-600 dark:bg-slate-900 dark:text-slate-300'}`}
              >
                {t(`settings.sections.${item}`)}
              </button>
            ))}
          </nav>
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <h2 className="text-lg font-semibold text-slate-950 dark:text-white">
              {t(`settings.sections.${section}`)}
            </h2>
            {section === 'processing_defaults' ? (
              <div className="mt-5">
                <ProcessOptionsFields
                  value={{ ...FALLBACK_OPTIONS, ...(draft as Partial<ProcessOptions>) }}
                  onChange={(next) => setValues(next as unknown as Values)}
                />
              </div>
            ) : (
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                {Object.entries(draft).map(([key, value]) => (
                  <SettingField
                    key={key}
                    name={key}
                    value={value}
                    onChange={(next) => update(key, next)}
                    t={t}
                  />
                ))}
              </div>
            )}
            <div className="mt-6 flex items-center gap-3">
              <button
                type="button"
                onClick={() => void save()}
                className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white"
              >
                {t('settings.save')}
              </button>
              {message && <span className="text-sm text-emerald-600">{message}</span>}
            </div>
            {section === 'telegram' && (
              <button
                type="button"
                onClick={() => void testTelegram()}
                disabled={testingTelegram}
                className="mt-3 rounded-xl border border-indigo-300 px-4 py-2.5 text-sm font-semibold text-indigo-600 disabled:opacity-50"
              >
                {testingTelegram ? t('settings.testingTelegram') : t('settings.testTelegram')}
              </button>
            )}
          </section>
        </div>
      )}
    </main>
  )
}

function SettingField({
  name,
  value,
  onChange,
  t,
}: {
  name: string
  value: unknown
  onChange: (value: unknown) => void
  t: (key: string) => string
}) {
  if (typeof value === 'boolean')
    return (
      <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
        <input type="checkbox" checked={value} onChange={(event) => onChange(event.target.checked)} />
        {t(`settings.fields.${name}`)}
      </label>
    )
  if (typeof value === 'number')
    return (
      <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
        {t(`settings.fields.${name}`)}
        <input
          type="number"
          value={value}
          onChange={(event) => onChange(Number(event.target.value))}
          className="mt-1.5 w-full rounded-lg border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
        />
      </label>
    )
  if (typeof value === 'object' && value !== null && 'configured' in value)
    return (
      <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
        {t(`settings.fields.${name}`)}
        <input
          type="password"
          placeholder={value.configured ? t('settings.configured') : t('settings.notConfigured')}
          onChange={(event) => onChange(event.target.value)}
          className="mt-1.5 w-full rounded-lg border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
        />
      </label>
    )
  const text = typeof value === 'string' ? value : JSON.stringify(value)
  return (
    <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
      {t(`settings.fields.${name}`)}
      <input
        value={text ?? ''}
        onChange={(event) => {
          if (typeof value !== 'object') onChange(event.target.value)
          else {
            try {
              onChange(JSON.parse(event.target.value) as unknown)
            } catch {
              /* JSON en edición */
            }
          }
        }}
        className="mt-1.5 w-full rounded-lg border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
      />
    </label>
  )
}
