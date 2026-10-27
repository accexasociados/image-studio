import { AppHeader } from '@/app/components/AppHeader'
import { useTheme } from '@/app/theme/useTheme'
import { BatchesPage } from '@/modules/batches/pages/BatchesPage'

export function App() {
  const { theme, toggleTheme } = useTheme()

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <AppHeader theme={theme} onToggleTheme={toggleTheme} />
      <BatchesPage />
    </div>
  )
}
