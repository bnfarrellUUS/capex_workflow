import { useLocation, useNavigate } from 'react-router-dom'
import { X } from 'lucide-react'
import { closeOpenRequest, useOpenRequests, type OpenRequest } from '../openRequests'

/* The request currently on screen, from the URL rather than from stored state:
   the address bar is the one place that cannot drift out of step with what is
   rendered. Both request pages count -- /requests/:id (view) and
   /requests/:id/edit (wizard) -- and /requests/new does not: a request with no
   id yet has no tab. */
const REQUEST_PATH = /^\/requests\/([^/]+)(?:\/edit)?$/

function activeRequestId(pathname: string): string | null {
  const id = REQUEST_PATH.exec(pathname)?.[1] ?? null
  return id === 'new' ? null : id
}

/* A tab remembers which page the person was on. */
function pathFor(tab: OpenRequest): string {
  return tab.mode === 'edit' ? `/requests/${tab.id}/edit` : `/requests/${tab.id}`
}

/* Where to go when the tab you are looking at is the one being closed: the tab
   to its right, else the one to its left, else nothing is left to show. */
function neighbourOf(tabs: OpenRequest[], id: string): OpenRequest | null {
  const at = tabs.findIndex((t) => t.id === id)
  if (at < 0) return null
  return tabs[at + 1] ?? tabs[at - 1] ?? null
}

export function RequestTabs({ userId }: { userId: string }) {
  const tabs = useOpenRequests(userId)
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const active = activeRequestId(pathname)

  // Nothing open means no strip at all, not an empty bar.
  if (tabs.length === 0) return null

  function close(tab: OpenRequest) {
    closeOpenRequest(userId, tab.id)
    if (tab.id !== active) return
    const next = neighbourOf(tabs, tab.id)
    navigate(next ? pathFor(next) : '/requests')
  }

  return (
    <div
      data-testid="request-tabs"
      className="flex min-w-0 items-stretch gap-1 overflow-x-auto border-b border-border bg-surface-2 px-3"
    >
      {tabs.map((tab) => {
        const current = tab.id === active
        return (
          /* Outlined pills, the current one FILLED in the accent: every tab
             carries a visible border, and the active one reads at a glance.
             bg-accent + text-accent-fg is the same active treatment the
             sidebar pill uses. */
          <span
            key={tab.id}
            className={`my-1 flex min-w-0 shrink-0 items-center rounded-md border ${
              current ? 'border-accent bg-accent' : 'border-border bg-surface'
            }`}
          >
            <button
              type="button"
              // Weight and the filled outline as well as colour -- never colour alone.
              aria-current={current ? 'page' : undefined}
              onClick={() => navigate(pathFor(tab))}
              className={`flex min-w-0 max-w-56 items-baseline gap-2 py-1.5 pl-2 pr-1 text-sm ${
                current
                  ? 'font-bold text-accent-fg'
                  : 'font-medium text-muted hover:text-fg'
              }`}
              title={tab.title ? `${tab.number} — ${tab.title}` : tab.number}
            >
              <span className="shrink-0">{tab.number}</span>
              {tab.title && (
                <span
                  className={`min-w-0 truncate text-xs ${
                    current ? 'text-accent-fg/80' : 'text-muted'
                  }`}
                >
                  {tab.title}
                </span>
              )}
            </button>
            <button
              type="button"
              aria-label={`Close ${tab.number}`}
              onClick={() => close(tab)}
              className={`mr-1 rounded p-1 ${
                current
                  ? 'text-accent-fg/80 hover:bg-white/20 hover:text-accent-fg'
                  : 'text-muted hover:bg-surface-2 hover:text-fg'
              }`}
            >
              <X size={14} />
            </button>
          </span>
        )
      })}
      <button
        type="button"
        aria-label="New request"
        onClick={() => navigate('/requests/new')}
        className="shrink-0 px-2 text-lg font-semibold leading-none text-muted hover:text-fg"
      >
        +
      </button>
    </div>
  )
}
