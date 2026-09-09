import { useQuery } from '@tanstack/react-query'

import { pingUnreadCount } from '../api/pings'

/** The 🔔 emoji is a deliberate exception to the custom-icon rule (spec
 *  section 8.2): the yellow bell is the recognisable affordance across ARIA,
 *  SCORE and CAPRI, and users move between the apps.
 *
 *  The count polls on a TanStack interval -- invalidate ['pings'] after any
 *  action and the badge updates at once instead of up to 30s later. */
export function PingBell({ onClick }: { onClick: () => void }) {
  const { data: unread = 0 } = useQuery({
    queryKey: ['pings', 'unread'],
    queryFn: pingUnreadCount,
    refetchInterval: 30_000,
  })

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Messages"
      title="Messages"
      className="relative rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm hover:bg-surface-2"
    >
      🔔
      {unread > 0 && (
        <span
          data-testid="ping-badge"
          className="absolute -right-2 -top-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white tabular-nums"
        >
          {unread > 99 ? '99+' : unread}
        </span>
      )}
    </button>
  )
}
