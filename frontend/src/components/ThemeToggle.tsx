import { useState } from 'react'
import { Moon, Sun } from 'lucide-react'
import { getTheme, toggleTheme } from '../theme'

export function ThemeToggle() {
  const [theme, setThemeState] = useState(getTheme())
  const isDark = theme === 'dark'
  return (
    <button
      type="button"
      onClick={() => setThemeState(toggleTheme())}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-3 py-1.5 text-sm font-medium text-fg transition hover:bg-surface-2"
    >
      {isDark ? <Sun size={15} /> : <Moon size={15} />}
      {isDark ? 'Light' : 'Dark'}
    </button>
  )
}
