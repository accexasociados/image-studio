import { AppHeader } from '@/app/components/AppHeader'
import { useTheme } from '@/app/theme/useTheme'
import { BatchesPage } from '@/modules/batches/pages/BatchesPage'
import { SettingsPage } from '@/modules/settings/pages/SettingsPage'
import { useState } from 'react'

export function App() {
  const { theme, toggleTheme } = useTheme()
  const [settings, setSettings] = useState(false)

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <AppHeader
        theme={theme}
        onToggleTheme={toggleTheme}
        onSettings={() => setSettings((value) => !value)}
      />
      {settings ? <SettingsPage onClose={() => setSettings(false)} /> : <BatchesPage />}
    </div>
  )
}
