import { AppHeader } from '@/app/components/AppHeader'
import { useTheme } from '@/app/theme/useTheme'
import { BatchesPage } from '@/modules/batches/pages/BatchesPage'
import { SettingsPage } from '@/modules/settings/pages/SettingsPage'
import { useState } from 'react'
import { useBrowserNotifications } from '@/app/hooks/useBrowserNotifications'

export function App() {
  const { theme, toggleTheme } = useTheme()
  const [settings, setSettings] = useState(false)
  const browserNotifications = useBrowserNotifications()

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <AppHeader
        theme={theme}
        onToggleTheme={toggleTheme}
        onSettings={() => setSettings((value) => !value)}
        notificationPermission={browserNotifications.permission}
        onEnableNotifications={browserNotifications.requestPermission}
      />
      {settings ? <SettingsPage onClose={() => setSettings(false)} /> : <BatchesPage />}
    </div>
  )
}
