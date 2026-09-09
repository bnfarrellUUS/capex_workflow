import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { useMe } from '../auth/useMe'
import { getPing, markPingDone, replyToPing, reopenPing } from '../api/pings'
import { formatActionDate } from '../routes/formatDate'
import { StatusBadge } from './ui/Badge'

const CHIP = 'inline-flex items-center gap-1.5 rounded-full border border-border px-2 py-0.5 text-[11px] text-muted'

/** The ping detail view: the note, the request it is about, the roster,
 *  replies, a reply box, and Done/Reopen. Hosted by PingPanel (slide-over) and
 *  MessagesPage (inline row expansion). */
export function PingDetail({ id, onBack, onNavigate }: {
  id: string
  onBack?: () => void
  /** Fired when the request link is followed, so a hosting overlay can close
   *  itself instead of sitting over the page it just navigated to. */
  onNavigate?: () => void
}) {
  const queryClient = useQueryClient()
  const me = useMe()
  const [note, setNote] = useState('')

  const { data: ping, isError } = useQuery({
    queryKey: ['pings', 'detail', id],
    queryFn: () => getPing(id),
  })

  // Fetching the detail is what stamps read server-side, so the bell and the
  // list must catch up -- once per successful load, not on every render, or a
  // reply's own refetch of this query would re-fire it forever.
  const invalidatedFor = useRef<string | null>(null)
  useEffect(() => {
    if (ping && invalidatedFor.current !== ping.id) {
      invalidatedFor.current = ping.id
      queryClient.invalidateQueries({ queryKey: ['pings', 'unread'] })
      queryClient.invalidateQueries({ queryKey: ['pings', 'list'] })
    }
  }, [ping, queryClient])

  function afterAction() {
    queryClient.invalidateQueries({ queryKey: ['pings'] })
  }

  const replyMutation = useMutation({
    mutationFn: (text: string) => replyToPing(id, text),
    onSuccess: () => { setNote(''); afterAction() },
  })
  const doneMutation = useMutation({ mutationFn: () => markPingDone(id), onSuccess: afterAction })
  const reopenMutation = useMutation({ mutationFn: () => reopenPing(id), onSuccess: afterAction })

  const back = onBack && (
    <button type="button" onClick={onBack}
      className="mb-3 self-start text-xs font-semibold text-muted hover:text-fg">
      ← Back
    </button>
  )

  if (isError) {
    return (
      <div className="flex flex-1 flex-col p-3 text-sm">
        {back}
        <p role="alert" className="text-xs text-red-600 dark:text-red-400">Could not load this ping.</p>
      </div>
    )
  }
  if (!ping) return <p className="p-3 text-xs text-muted">Loading…</p>

  const mine = ping.recipients.find((r) => r.user_id === me.data?.id)
  const trimmed = note.trim()
  const req = ping.request

  return (
    <div className="flex flex-1 flex-col overflow-y-auto p-3 text-sm">
      {back}

      <div className="mb-1 flex items-center gap-2">
        <span className="text-xs font-bold">{ping.sender.name}</span>
        <span className="text-[10px] text-muted">{formatActionDate(ping.created_at)}</span>
      </div>
      <p className="mb-3 whitespace-pre-wrap text-sm leading-relaxed">{ping.note}</p>

      {req && (
        <div className="mb-3 flex flex-wrap items-center gap-1.5">
          {req.visible ? (
            <Link to={`/requests/${req.id}`} onClick={onNavigate}
              className="inline-flex items-center gap-1.5 rounded-full border border-accent px-2 py-0.5 text-[11px] text-accent">
              {req.number} <StatusBadge status={req.status} />
            </Link>
          ) : (
            <span className={CHIP}>{req.number} <StatusBadge status={req.status} /></span>
          )}
          <span className="text-[11px] text-muted">
            {req.requestor_name ?? '—'} · {req.division_name ?? '—'} · ${Number(req.total_cost ?? 0).toLocaleString()}
          </span>
        </div>
      )}

      <div className="mb-3 border-t border-border pt-2">
        <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted">Roster</div>
        {ping.recipients.map((r) => (
          <div key={r.user_id} className="flex items-center justify-between py-0.5 text-xs">
            <span>{r.name}</span>
            <span className="text-muted">{r.completed_at ? 'done' : r.read_at ? 'read' : ''}</span>
          </div>
        ))}
      </div>

      {ping.replies.length > 0 && (
        <div className="mb-3 border-t border-border pt-2">
          {ping.replies.map((r) => (
            <div key={r.id} className="mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold">{r.sender.name}</span>
                <span className="text-[10px] text-muted">{formatActionDate(r.created_at)}</span>
              </div>
              <p className="whitespace-pre-wrap text-xs leading-relaxed text-fg/80">{r.note}</p>
            </div>
          ))}
        </div>
      )}

      <div className="mt-auto border-t border-border pt-2">
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          placeholder="Reply…"
          className="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-xs outline-none placeholder:text-muted focus:border-accent"
        />
        <div className="mt-2 flex items-center justify-between gap-2">
          <button
            type="button"
            disabled={!trimmed || replyMutation.isPending}
            onClick={() => trimmed && replyMutation.mutate(trimmed)}
            className="rounded-md bg-accent px-2.5 py-1 text-xs font-semibold text-accent-fg disabled:opacity-50"
          >
            Send
          </button>
          <div className="flex items-center gap-2">
            {ping.done_by && <span className="text-[10px] text-muted">Done by {ping.done_by}</span>}
            {mine && (mine.completed_at ? (
              <button type="button" onClick={() => reopenMutation.mutate()}
                className="text-xs font-semibold text-muted hover:text-fg">Reopen</button>
            ) : (
              <button type="button" onClick={() => doneMutation.mutate()}
                className="text-xs font-semibold text-accent">Mark done</button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
