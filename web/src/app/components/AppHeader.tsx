import { Languages, Moon, Settings, Sparkles, Sun } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { Language } from '@/app/i18n/translations'
import { saveLanguage } from '@/app/i18n/i18n'
import type { Theme } from '@/app/theme/useTheme'

interface AppHeaderProps {
  theme: Theme
  onToggleTheme: () => void
  onSettings: () => void
}

export function AppHeader({ theme, onToggleTheme, onSettings }: AppHeaderProps) {
  const { t, i18n } = useTranslation()

  const changeLanguage = (language: Language) => {
    void i18n.changeLanguage(language)
    saveLanguage(language)
  }

  const themeLabel = theme === 'light' ? t('common.enableDarkTheme') : t('common.enableLightTheme')

  return (
    <header className="border-b border-slate-200/80 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90">
      <div className="mx-auto flex min-h-18 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-indigo-600 text-white shadow-sm shadow-indigo-600/30">
            <Sparkles size={20} aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="truncate text-base font-bold tracking-tight text-slate-950 dark:text-white">
              {t('app.title')}
            </p>
            <p className="hidden truncate text-xs text-slate-500 sm:block dark:text-slate-400">
              {t('app.workspace')}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <label className="relative flex items-center">
            <Languages
              size={16}
              className="pointer-events-none absolute left-3 text-slate-500 dark:text-slate-400"
              aria-hidden
            />
            <span className="sr-only">{t('common.language')}</span>
            <select
              aria-label={t('common.language')}
              className="h-10 appearance-none rounded-xl border border-slate-200 bg-white py-2 pr-3 pl-9 text-sm font-medium text-slate-700 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
              value={i18n.language}
              onChange={(event) => changeLanguage(event.target.value as Language)}
            >
              <option value="es">{t('common.spanish')}</option>
              <option value="en">{t('common.english')}</option>
            </select>
          </label>
          <button
            type="button"
            aria-label={themeLabel}
            title={themeLabel}
            onClick={onToggleTheme}
            className="grid size-10 place-items-center rounded-xl border border-slate-200 bg-white text-slate-600 transition hover:border-indigo-300 hover:text-indigo-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-indigo-600 dark:hover:text-indigo-400"
          >
            {theme === 'light' ? <Moon size={18} aria-hidden /> : <Sun size={18} aria-hidden />}
          </button>
          <button
            type="button"
            onClick={onSettings}
            aria-label={t('settings.title')}
            title={t('settings.title')}
            className="grid size-10 place-items-center rounded-xl border border-slate-200 bg-white text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
          >
            <Settings size={18} aria-hidden />
          </button>
        </div>
      </div>
    </header>
  )
}
