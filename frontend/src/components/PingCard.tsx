import type { PingSummary } from '../api/pings'
import { formatActionDate } from '../routes/formatDate'

export type Box = 'inbox' | 'sent'

/** Inbox names the sender; Sent names the recipients (never the viewer, who is
 *  always the sender on a Sent card). */
export function who(ping: PingSummary, box: Box): string {
  if (box === 'inbox') return ping.sender.name
  const names = ping.recipients.map((r) => r.name)
  return names.length > 2 ? `→ ${names.slice(0, 2).join(', ')} +${names.length - 2}` : `→ ${names.join(', ')}`
}

const PILL: Record<string, string> = {
  unread: 'text-accent border-accent',
  read: 'text-muted border-muted',
  done: 'text-green-700 border-green-700 dark:text-green-400 dark:border-green-400',
}

export function statusOf(ping: PingSummary): 'unread' | 'read' | 'done' {
  if (ping.completed_at) return 'done'
  return ping.unread_for_me ? 'unread' : 'read'
}

/** Status pills are OUTLINED, never filled -- three filled blocks compete with
 *  the table they sit in (spec section 8.8). */
export function PingStatusPill({ ping }: { ping: PingSummary }) {
  const status = statusOf(ping)
  return (
    <span className={`inline-block rounded-lg border px-1.5 py-px text-[10px] font-bold ${PILL[status]}`}>
      {status}
    </span>
  )
}

export function PingCard({ ping, box, onOpen }: { ping: PingSummary; box: Box; onOpen: () => void }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className={`mb-2 w-full rounded-lg border p-3 text-left ${
        ping.unread_for_me ? 'border-accent bg-accent/5' : 'border-border bg-surface'
      }`}
    >
      <div className="mb-1 flex items-center gap-2">
        <span className="flex-1 truncate text-xs font-bold">{who(ping, box)}</span>
        <span className="whitespace-nowrap text-[10px] text-muted">{formatActionDate(ping.last_activity_at)}</span>
        <PingStatusPill ping={ping} />
      </div>
      <div className="text-xs leading-relaxed text-fg/80">{ping.note}</div>
      {ping.request && (
        <div className="mt-1 text-[10px] text-muted">{ping.request.number}</div>
      )}
      {ping.done_by && <div className="mt-1.5 text-[10px] text-muted">Done by {ping.done_by}</div>}
    </button>
  )
}
